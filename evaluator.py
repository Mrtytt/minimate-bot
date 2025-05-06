import chess.pgn
from stockfish import Stockfish
import chess.polyglot
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import copy
from game_tracker import is_already_analyzed, mark_as_analyzed

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
    def is_endgame(board):
        """Basit materyal sayımına göre oyun sonu kontrolü."""
        total_material = sum(piece.piece_type != chess.KING for piece in board.piece_map().values())
        return total_material <= 6  # örnek eşik: sadece birkaç taş kaldıysa

    def is_minor_piece(move, board):
        piece = board.piece_at(move.from_square)
        return piece and piece.piece_type in [chess.KING, chess.PAWN]

    if board and move:
        if is_sacrifice(board, move) and eval_diff >= 0 and diff == 0:
            if not is_endgame(board) and not is_minor_piece(move, board):
                return "Brilliant"
        elif is_sacrifice(board, move) and eval_diff >= 0 and diff <= 10:
            if not is_endgame(board) or not is_minor_piece(move, board):
                return "Great"

    if diff < 20:
        return "Best"
    elif diff < 35:
        return "Excellent"
    elif diff < 75:
        return "Good"
    elif diff < 150:
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
            best_move_san = best_move_uci
    except:
        best_move_san = best_move_uci
    best_cp = best_eval.get("value") if best_eval["type"] == "cp" else None

    played_move_san = board.san(move)
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
        "played_san": played_move_san,
        "best": best_move_san,
        "eval": played_eval,
        "type": move_type,
        "book": book_move,
        "fen": board_fen
    }

def evaluate_game_parallel(pgn_path, white_player, black_player):
    with open(pgn_path) as pgn_file:
        pgn_text = pgn_file.read()

    # Önceden analiz kontrolü
    existing_analysis = is_already_analyzed(pgn_text)
    if existing_analysis:
        print("Bu oyun daha önce analiz edilmiş.")
        return (
            existing_analysis.get("results"),
            existing_analysis.get("move_stats"),
            existing_analysis.get("accuracy_scores")
        )

    # Yeni analiz işlemi
    game = chess.pgn.read_game(open(pgn_path))
    board = game.board()
    tasks = []
    move_list = list(game.mainline_moves())

    for idx, move in enumerate(move_list):
        fen = board.fen()
        tasks.append((idx + 1, fen, move.uci()))
        board.push(move)

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda args: analyze_move(*args), tasks))

    results.sort(key=lambda x: x["index"])

    move_stats = {
        white_player: defaultdict(int),
        black_player: defaultdict(int)
    }

    board = game.board()
    for result in results:
        move = chess.Move.from_uci(result["played"])
        if move not in board.legal_moves:
            raise ValueError(f"Geçersiz hamle: {move}")
        board.push(move)

        player = white_player if board.turn == chess.BLACK else black_player
        move_stats[player][result["type"]] += 1

    weights = {
        "Brilliant": 1.1, "Great": 1.05, "Best": 1.0, "Excellent": 0.95,
        "Good": 0.5, "Inaccuracy": 0.35, "Mistake": 0.15, "Blunder": 0.0,
        "Forced Mate": 1.0, "Missed Win": 0.1, "Book": 1.0
    }

    accuracy_scores = {}
    for player, stats in move_stats.items():
        total_moves = sum(stats.values())
        weighted_sum = sum(count * weights.get(t, 0.5) for t, count in stats.items())
        accuracy = (weighted_sum / total_moves) * 100 if total_moves > 0 else 0
        accuracy_scores[player] = round(min(accuracy, 100), 2)

    # Ön belleğe analiz sonucunu kaydet
    mark_as_analyzed(pgn_text, {
        "white": white_player,
        "black": black_player,
        "results": results,
        "move_stats": {p: dict(move_stats[p]) for p in move_stats},
        "accuracy_scores": accuracy_scores
    })

    return results, move_stats, accuracy_scores
