from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcards.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ------------------------------
# Database Model
# ------------------------------
class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------------
# Subject Classification
# ------------------------------
subject_keywords = {
    "Physics": ["force", "acceleration", "energy", "motion", "wave", "electricity", "gravity", "newton", "velocity"],
    "Chemistry": ["atom", "molecule", "reaction", "acid", "base", "compound", "element", "periodic"],
    "Biology": ["cell", "photosynthesis", "ecosystem", "dna", "evolution", "gene", "plant", "organism"],
    "Mathematics": ["equation", "algebra", "calculus", "geometry", "statistics", "number", "integral"],
    "History": ["war", "empire", "revolution", "ancient", "battle", "king", "historical", "colonial"],
    "Geography": ["continent", "country", "mountain", "river", "ocean", "climate", "landform", "region"],
    "Literature": ["novel", "poem", "author", "prose", "drama", "literary", "character", "metaphor"],
    "Computer Science": ["programming", "algorithm", "data structure", "loop", "python", "variable", "array"]
}

def classify_subject(text):
    text = text.lower()
    scores = {subject: 0 for subject in subject_keywords}
    
    for subject, keywords in subject_keywords.items():
        for keyword in keywords:
            scores[subject] += len(re.findall(r'\b' + re.escape(keyword) + r'\b', text))
    
    best_subject = max(scores, key=scores.get)
    return best_subject if scores[best_subject] > 0 else "General"

# ------------------------------
# Routes
# ------------------------------

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "message": "Smart Flashcard API is running"})

@app.route("/flashcard", methods=["POST"])
def add_flashcard():
    data = request.get_json()
    required_fields = ["student_id", "question", "answer"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    combined_text = f"{data['question']} {data['answer']}"
    subject = classify_subject(combined_text)

    flashcard = Flashcard(
        student_id=data["student_id"],
        question=data["question"],
        answer=data["answer"],
        subject=subject
    )
    db.session.add(flashcard)
    db.session.commit()

    return jsonify({
        "message": "Flashcard added successfully",
        "subject": subject,
        "flashcard_id": flashcard.id
    })

@app.route("/flashcards/<subject>", methods=["GET"])
def get_flashcards_by_subject(subject):
    limit = int(request.args.get("limit", 10))
    student_id = request.args.get("student_id")

    query = Flashcard.query.filter_by(subject=subject)
    if student_id:
        query = query.filter_by(student_id=student_id)

    flashcards = query.order_by(Flashcard.created_at.desc()).limit(min(limit, 100)).all()

    return jsonify({
        "subject": subject,
        "count": len(flashcards),
        "flashcards": [serialize_flashcard(f) for f in flashcards]
    })

@app.route("/flashcards/mixed", methods=["GET"])
def get_mixed_flashcards():
    limit = int(request.args.get("limit", 10))
    student_id = request.args.get("student_id")
    subject_counts = {}

    results = []
    per_subject = max(1, limit // len(subject_keywords))

    for subject in subject_keywords:
        query = Flashcard.query.filter_by(subject=subject)
        if student_id:
            query = query.filter_by(student_id=student_id)
        subset = query.order_by(func.random()).limit(per_subject).all()
        if subset:
            subject_counts[subject] = len(subset)
            results.extend(subset)

    # Shuffle results and cap at limit
    from random import shuffle
    shuffle(results)
    results = results[:limit]

    return jsonify({
        "count": len(results),
        "flashcards": [serialize_flashcard(f) for f in results],
        "subjects_included": list(subject_counts.keys())
    })

@app.route("/flashcards", methods=["GET"])
def get_all_flashcards():
    limit = int(request.args.get("limit", 10))
    student_id = request.args.get("student_id")

    query = Flashcard.query
    if student_id:
        query = query.filter_by(student_id=student_id)

    flashcards = query.order_by(Flashcard.created_at.desc()).limit(min(limit, 100)).all()
    return jsonify({
        "count": len(flashcards),
        "flashcards": [serialize_flashcard(f) for f in flashcards]
    })

@app.route("/subjects", methods=["GET"])
def get_subjects():
    subjects = db.session.query(
        Flashcard.subject, func.count(Flashcard.id)
    ).group_by(Flashcard.subject).all()

    return jsonify({
        "subjects": [s[0] for s in subjects],
        "subject_counts": {s[0]: s[1] for s in subjects}
    })

# ------------------------------
# Utility
# ------------------------------

def serialize_flashcard(flashcard):
    return {
        "id": flashcard.id,
        "student_id": flashcard.student_id,
        "question": flashcard.question,
        "answer": flashcard.answer,
        "subject": flashcard.subject,
        "created_at": flashcard.created_at.isoformat()
    }

# ------------------------------
# Run App
# ------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
