from flask import Flask, render_template, request
from evaluator import evaluate_game_parallel
import os
from werkzeug.utils import secure_filename
import chess.pgn

UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["pgnfile"]
        if file.filename.endswith(".pgn"):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            # Oyuncu adlarını PGN'den çek
            with open(filepath) as f:
                game = chess.pgn.read_game(f)
                white_player = game.headers.get("White", "Beyaz")
                black_player = game.headers.get("Black", "Siyah")

            # Değerlendirme + hamle istatistiklerini al
            results, move_stats, accuracy_scores = evaluate_game_parallel(filepath, white_player, black_player)

            return render_template("index.html",
                                   results=results,
                                   filename=filename,
                                   accuracy_scores=accuracy_scores,
                                   white_player=white_player,
                                   black_player=black_player,
                                   move_stats=move_stats)
    return render_template("index.html", results=None)

if __name__ == "__main__":
    app.run(debug=True)