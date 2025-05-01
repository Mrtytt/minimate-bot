# evaluator.py
import chess.pgn
from stockfish import Stockfish
import chess.polyglot
from collections import defaultdict

stockfish = Stockfish(path="C:/ChessEngines/stockfish/stockfish.exe", depth=15)
stockfish.set_skill_level(15)

def is_book_move(board, book_path="C:/ChessEngines/openings/komodo.bin"):
    try:
        with chess.polyglot.open_reader(book_path) as reader:
            return any(reader.find_all(board))
    except Exception as e:
        print(f"Book error: {e}")
        return False

def classify_move(eval_diff, played_eval, best_eval, is_mate=False, book_move=False):
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

    if diff == 0:
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

def evaluate_game(pgn_path, white_player, black_player):
    with open(pgn_path) as pgn:
        game = chess.pgn.read_game(pgn)
        board = game.board()

        results = []
        move_number = 1

        # Hamle türü istatistikleri
        move_stats = {
            white_player: defaultdict(int),
            black_player: defaultdict(int)
        }

        for move in game.mainline_moves():
            # En iyi hamleyi oynanmadan önce al
            stockfish.set_fen_position(board.fen())
            best_move_uci = stockfish.get_best_move()
            best_eval = stockfish.get_evaluation()

            try:
                best_move_obj = chess.Move.from_uci(best_move_uci)
                best_move_san = board.san(best_move_obj)
            except:
                best_move_san = best_move_uci

            # Oynanan hamleyi uygula
            san_move = board.san(move)
            board.push(move)

            # Hamle sonrası değerlendirme
            stockfish.set_fen_position(board.fen())
            played_eval = stockfish.get_evaluation()
            played_cp = played_eval.get("value") if played_eval["type"] == "cp" else None
            is_mate = played_eval["type"] == "mate"

            best_cp = best_eval.get("value") if best_eval["type"] == "cp" else None
            eval_diff = played_cp - best_cp if (played_cp is not None and best_cp is not None) else None

            # Kitap hamlesi mi?
            book_move = is_book_move(board) if move_number <= 6 else False

            # Hamle türü
            move_type = classify_move(eval_diff, played_cp, best_cp, is_mate, book_move)

            results.append({
                "move_number": move_number,
                "played": san_move,
                "best": best_move_san,
                "eval": played_eval,
                "type": move_type,
                "book": book_move
            })

            # Sıra beyazda ise önce siyah oynadı
            player = white_player if board.turn == chess.BLACK else black_player
            move_stats[player][move_type] += 1

            move_number += 1

        return results, move_stats