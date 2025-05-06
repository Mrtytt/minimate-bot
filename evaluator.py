import chess.pgn
from stockfish import Stockfish
import chess.polyglot
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import copy

# Ana motor örneği sadece path için kullanılacak
STOCKFISH_PATH = "C:/ChessEngines/stockfish/stockfish.exe"
BOOK_PATH = "C:/ChessEngines/openings/komodo.bin"

def is_book_move(board):
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            return any(reader.find_all(board))
    except:
        return False

def is_sacrifice(board, move):
    if board.is_capture(move):
        captured_piece = board.piece_at(move.to_square)
        moving_piece = board.piece_at(move.from_square)
        if captured_piece and moving_piece:
            return moving_piece.piece_type > captured_piece.piece_type
    return False

def classify_move(eval_diff, played_eval, best_eval, is_mate=False, book_move=False,
                  board=None, move=None):
    if book_move:
        return "Book"
    if is_mate:
        if best_eval is not None and best_eval < 0:
            return "Missed Win"
        else:
            return "Forced Mate"
    if eval_diff is None:
        return "Unknown"

    diff = abs(eval_diff)

    # Brilliant: Taş fedası ve çok iyi hamle olmalı
    if board and move:
        if is_sacrifice(board, move) and eval_diff >= 0 and diff < 50:
            return "Brilliant"

    if diff == 0:
        return "Great"
    elif diff < 10:
        return "Best"
    elif diff < 20:
        return "Excellent"
    elif diff < 50:
        return "Good"
    elif diff < 100:
        return "Inaccuracy"
    elif diff < 300:
        return "Mistake"
    else:
        return "Blunder"

def analyze_move(index, board_fen, move_uci):
    board = chess.Board(board_fen)
    move = chess.Move.from_uci(move_uci)
    stockfish = Stockfish(path=STOCKFISH_PATH, depth=18)  # depth=24 olarak ayarlandı
    stockfish.set_fen_position(board.fen())

    best_move_uci = stockfish.get_best_move()
    best_eval = stockfish.get_evaluation()

    try:
        best_move_obj = chess.Move.from_uci(best_move_uci)
        if best_move_obj in board.legal_moves:
            best_move_san = board.san(best_move_obj)
        else:
            best_move_san = best_move_uci  # Yine de fallback kalsın
    except:
        best_move_san = best_move_uci
    best_cp = best_eval.get("value") if best_eval["type"] == "cp" else None

    board.push(move)

    stockfish.set_fen_position(board.fen())
    played_eval = stockfish.get_evaluation()
    played_cp = played_eval.get("value") if played_eval["type"] == "cp" else None
    is_mate = played_eval["type"] == "mate"

    eval_diff = played_cp - best_cp if (played_cp is not None and best_cp is not None) else None
    book_move = is_book_move(chess.Board(board_fen)) if index <= 6 else False

    move_type = classify_move(eval_diff, played_cp, best_cp, is_mate,
                              book_move, chess.Board(board_fen), move)

    return {
        "index": index,
        "played": move_uci,
        "best": best_move_san,
        "eval": played_eval,
        "type": move_type,
        "book": book_move,
        "fen": board_fen
    }

def evaluate_game_parallel(pgn_path, white_player, black_player):
    with open(pgn_path) as pgn:
        game = chess.pgn.read_game(pgn)
        board = game.board()

        tasks = []
        boards = []
        move_list = list(game.mainline_moves())

        # Hamleler ve board pozisyonları hazırlanıyor
        for idx, move in enumerate(move_list):
            fen = board.fen()
            tasks.append((idx + 1, fen, move.uci()))
            board.push(move)

        # Paralel analiz başlatılıyor
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda args: analyze_move(*args), tasks))

        # Sonuçları sıralıyoruz (çünkü paralel işlem sırasını karıştırabilir)
        results.sort(key=lambda x: x["index"])

        # İstatistikleri çıkar
        move_stats = {
            white_player: defaultdict(int),
            black_player: defaultdict(int)
        }

        board = game.board()
        for result in results:
            move = chess.Move.from_uci(result["played"])
            board.push(move)

            player = white_player if board.turn == chess.BLACK else black_player
            move_stats[player][result["type"]] += 1

        # Ağırlıklı skor hesaplama
        weights = {
            "Brilliant": 1.1,   # Mükemmel hamleler, yüksek ama çok abartılmadan
            "Great": 1.05,       # Çok iyi hamleler
            "Best": 0.95,        # En iyi hamleler, temel kabul
            "Excellent": 0.85,   # İyi hamleler ama çok etkili değil
            "Good": 0.5,        # "Good" hamlelerin etkisini biraz azaltıyoruz
            "Inaccuracy": 0.2,  # Inaccuracy, negatif etkisi yüksek
            "Mistake": 0.1,     # Mistake, doğruluğu daha çok etkiliyor
            "Blunder": 0.0,     # Blunder, doğruluğu çok ciddi şekilde etkiliyor
            "Forced Mate": 1.0, # Zorunlu matlar, yüksek ağırlık
            "Missed Win": 0.1,  # Kaçırılmış zaferler, çok düşük etkisi var
            "Book": 1.0         # Kitap hamleleri, etkisi orta seviyede
        }

        accuracy_scores = {}
        for player, stats in move_stats.items():
            total_moves = sum(stats.values())
            weighted_sum = sum(count * weights.get(move_type, 0.5) for move_type, count in stats.items())
            accuracy = (weighted_sum / total_moves) * 100 if total_moves > 0 else 0
            accuracy_scores[player] = round(min(accuracy, 100), 2)

        return results, move_stats, accuracy_scores
