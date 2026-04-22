from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import chess
import chess.pgn
import chess.engine
import chess.svg
import io
import os

app = Flask(__name__)
CORS(app)

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

def cp(score_obj):
    if score_obj is None:
        return None
    return score_obj.white().score(mate_score=10000)

def material(board, color):
    return sum(len(board.pieces(pt, color)) * val for pt, val in PIECE_VALUES.items())

def attacked_pieces(board, color):
    return [
        sq for sq, piece in board.piece_map().items()
        if piece.color == color and board.is_attacked_by(not color, sq)
    ]

def make_puzzle(board, move, label):
    return {
        "fen": board.fen(),
        "answer": board.san(move),
        "side": "White" if board.turn == chess.WHITE else "Black",
        "svg": chess.svg.board(board=board, size=420, flipped=(board.turn == chess.BLACK)),
        "label": label
    }

def is_underpromotion(move):
    return move.promotion and move.promotion != chess.QUEEN

def is_danger_entry(board, move):
    temp = board.copy()
    temp.push(move)
    return temp.is_attacked_by(not board.turn, move.to_square)

def ignores_attacked_piece(board, move):
    attacked = attacked_pieces(board, board.turn)
    return attacked and move.from_square not in attacked

def eval_after_best(board, best_move):
    temp = board.copy()
    temp.push(best_move)
    info = engine.analyse(temp, chess.engine.Limit(depth=8))
    return cp(info["score"])

def extract_puzzles(pgn_text):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return []

    board = game.board()
    brilliant, onlymove = [], []
    fallback, best_gap = None, -1

    for move in game.mainline_moves():
        analysis = engine.analyse(board, chess.engine.Limit(depth=10), multipv=2)

        if not analysis or "pv" not in analysis[0]:
            board.push(move)
            continue

        best_move = analysis[0]["pv"][0]
        best_score = cp(analysis[0]["score"])
        second_score = cp(analysis[1]["score"]) if len(analysis) > 1 else None

        board.push(move)
        played_score = cp(engine.analyse(board, chess.engine.Limit(depth=8))["score"])
        board.pop()

        if best_score is None or played_score is None:
            board.push(move)
            continue

        gap = abs(best_score - played_score)

        # fallback 저장
        if gap > best_gap:
            best_gap = gap
            fallback = make_puzzle(board, best_move, "가장 중요한 수")

        # 포지션 너무 기울어진 경우 제외
        if not (-500 < best_score < 500):
            board.push(move)
            continue

        # ===== 탁월수 판정 =====
        after_score = eval_after_best(board, best_move)

        brilliant_flag = False

        if gap >= 120 and after_score is not None:
            if is_underpromotion(best_move):
                brilliant_flag = True

            elif is_danger_entry(board, best_move):
                if after_score >= best_score - 80:
                    brilliant_flag = True

            elif ignores_attacked_piece(board, best_move):
                if after_score >= best_score - 80:
                    brilliant_flag = True

        if brilliant_flag:
            brilliant.append(make_puzzle(board, best_move, "놓친 탁월수 !!"))
            board.push(move)
            continue

        # ===== 유일수 판정 =====
        if second_score is not None:
            if abs(best_score - second_score) >= 180 and gap >= 100:
                onlymove.append(make_puzzle(board, best_move, "놓친 유일수 !"))
                board.push(move)
                continue

        board.push(move)

    if brilliant:
        return brilliant[:3]
    if onlymove:
        return onlymove[:3]
    if fallback:
        return [fallback]

    return []

@app.route("/")
def home():
    return send_file("puzzle.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    return jsonify(extract_puzzles(data.get("pgn", "")))

if __name__ == "__main__":
    app.run()
