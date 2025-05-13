from evaluator import evaluate_game_parallel
import os
from werkzeug.utils import secure_filename
import chess.pgn
from flask import Flask, render_template, request, session, redirect, url_for
import pickle

UPLOAD_FOLDER = 'uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = os.urandom(24)  # rastgele güvenli anahtar üretir

@app.route("/", methods=["GET", "POST"])
def index():
    PER_PAGE = 20

    if request.method == "POST":
        file = request.files["pgnfile"]
        if file.filename.endswith(".pgn"):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            with open(filepath) as f:
                game = chess.pgn.read_game(f)
                white_player = game.headers.get("White", "Beyaz")
                black_player = game.headers.get("Black", "Siyah")

            results, move_stats, accuracy_scores = evaluate_game_parallel(filepath, white_player, black_player)

            # Veriyi session içinde sakla (pickle ile çünkü liste saklıyoruz)
            session["results"] = pickle.dumps(results)
            session["white_player"] = white_player
            session["black_player"] = black_player
            session["accuracy_scores"] = accuracy_scores
            session["move_stats"] = move_stats
            session["filename"] = filename

            return redirect(url_for("index", page=1))

    # GET İSTEĞİ (sayfalama)
    if "results" in session:
        page = int(request.args.get("page", 1))
        results = pickle.loads(session["results"])
        filename = session["filename"]
        white_player = session["white_player"]
        black_player = session["black_player"]
        accuracy_scores = session["accuracy_scores"]
        move_stats = session["move_stats"]

        total_pages = (len(results) - 1) // PER_PAGE + 1
        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE
        paginated_results = results[start:end]

        return render_template("index.html",
                               results=paginated_results,
                               filename=filename,
                               accuracy_scores=accuracy_scores,
                               white_player=white_player,
                               black_player=black_player,
                               move_stats=move_stats,
                               page=page,
                               total_pages=total_pages)

    # Hiç dosya yüklenmemişse
    return render_template("index.html", results=None)

if __name__ == "__main__":
    app.run(debug=True)