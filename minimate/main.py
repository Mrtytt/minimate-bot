import chess.pgn
from stockfish import Stockfish

# Stockfish motorunun yolu (kendi yolunla değiştir)
stockfish_path = "C:/ChessEngines/stockfish/stockfish.exe"

stockfish = Stockfish(path=stockfish_path, depth=15)
stockfish.set_skill_level(15)


def classify_move(eval_diff, played_eval, best_eval, is_mate=False):
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


def evaluate_game(pgn_path):
    with open(pgn_path) as pgn:
        game = chess.pgn.read_game(pgn)
        board = game.board()

        print("Game loaded. Starting analysis...\n")
        move_number = 1

        for move in game.mainline_moves():
            san_move = board.san(move)
            board.push(move)

            # Şu andaki hamle sonrası pozisyonu değerlendir
            stockfish.set_fen_position(board.fen())
            evaluation = stockfish.get_evaluation()
            played_eval = evaluation.get("value") if evaluation["type"] == "cp" else None
            is_mate = evaluation["type"] == "mate"

            # En iyi hamleyi al
            best_move_uci = stockfish.get_best_move()
            try:
                best_move_obj = chess.Move.from_uci(best_move_uci)
                best_move_san = board.san(best_move_obj)
            except:
                best_move_san = best_move_uci

            # En iyi hamlenin değerlendirmesi
            board.pop()  # hamleyi geri al
            stockfish.set_fen_position(board.fen())
            best_eval_raw = stockfish.get_evaluation()
            board.push(move)  # hamleyi geri koy

            best_eval = best_eval_raw.get("value") if best_eval_raw["type"] == "cp" else None

            eval_diff = None
            if played_eval is not None and best_eval is not None:
                eval_diff = played_eval - best_eval

            move_type = classify_move(eval_diff, played_eval, best_eval, is_mate)

            print(f"{move_number}. Played: {san_move}, Best: {best_move_san}, Eval: {evaluation}, Type: {move_type}")
            move_number += 1


# Örnek kullanım
evaluate_game("C:/Users/Murat Berk/Documents/GitHub/minimate-bot/matches/tredibi_vs_YttMurat_2025.04.30.pgn")
