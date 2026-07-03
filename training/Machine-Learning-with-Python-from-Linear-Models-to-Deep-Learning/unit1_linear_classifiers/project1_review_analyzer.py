"""
Unit 1 PROJECT: Automatic Review Analyzer.

Run:  python project1_review_analyzer.py

Builds a sentiment classifier that predicts whether a review is positive or
negative, using your from-scratch Pegasos SVM on bag-of-words features.

This version ships with a small built-in dataset so it runs instantly with no
download. To use the real, full-size dataset, see the note at the bottom.
"""
import numpy as np
from svm_pegasos import pegasos_train, predict


# A built-in dataset so the file runs out of the box (1 = positive, -1 = negative).
# Positive and negative reviews use distinct sentiment words so the model can
# generalize to held-out examples.
REVIEWS = [
    ("fantastic wonderful film brilliant and amazing", 1),
    ("amazing brilliant acting wonderful and superb", 1),
    ("loved this great wonderful and fantastic story", 1),
    ("excellent beautiful brilliant and superb direction", 1),
    ("wonderful heartwarming enjoyable and delightful", 1),
    ("masterpiece brilliant wonderful and excellent", 1),
    ("superb performances gripping wonderful and amazing", 1),
    ("delightful funny moving brilliant and wonderful", 1),
    ("great fantastic enjoyable superb and beautiful", 1),
    ("brilliant amazing wonderful excellent and superb", 1),
    ("loved the beautiful and delightful wonderful film", 1),
    ("fantastic superb gripping and truly excellent", 1),
    ("enjoyable heartwarming wonderful great and amazing", 1),
    ("brilliant beautiful moving excellent and superb", 1),
    ("terrible awful film boring and dreadful", -1),
    ("awful boring lifeless terrible and dull", -1),
    ("hated this dull boring terrible and slow", -1),
    ("horrible terrible boring dreadful and awful", -1),
    ("disappointing terrible boring awful and dull", -1),
    ("bad boring forgettable terrible and dreadful", -1),
    ("dreadful boring awful terrible and painful", -1),
    ("worst awful boring pointless and terrible", -1),
    ("dull lifeless boring dreadful and awful", -1),
    ("terrible bad boring awful and disappointing", -1),
    ("boring slow dreadful terrible and lifeless", -1),
    ("awful dull terrible pointless and boring", -1),
    ("horrible dreadful boring bad and terrible", -1),
    ("painful boring awful terrible and forgettable", -1),
]


# Common filler words carry no sentiment, so we drop them.
STOPWORDS = {"and", "the", "a", "this", "of", "with", "to", "i", "was", "truly"}


def tokenize(text):
    return [w for w in text.split() if w not in STOPWORDS]


def build_vocabulary(texts):
    vocab = {}
    for t in texts:
        for word in tokenize(t):
            if word not in vocab:
                vocab[word] = len(vocab)
    return vocab


def bag_of_words(text, vocab):
    vec = np.zeros(len(vocab))
    for word in tokenize(text):
        if word in vocab:
            vec[vocab[word]] += 1
    return vec


def main():
    texts = [r[0] for r in REVIEWS]
    labels = np.array([r[1] for r in REVIEWS])

    vocab = build_vocabulary(texts)
    X = np.array([bag_of_words(t, vocab) for t in texts])

    # Simple train/test split.
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(X))
    split = int(0.75 * len(X))
    train, test = idx[:split], idx[split:]

    w, b = pegasos_train(X[train], labels[train], lambda_reg=0.01, epochs=100)
    train_acc = (predict(X[train], w, b) == labels[train]).mean()
    test_acc = (predict(X[test], w, b) == labels[test]).mean()

    print(f"Vocabulary size: {len(vocab)} words")
    print(f"Training accuracy: {train_acc:.2%}")
    print(f"Test accuracy:     {test_acc:.2%}")

    # Show the words the model thinks are most positive and most negative.
    order = np.argsort(w)
    inv_vocab = {v: k for k, v in vocab.items()}
    print("\nMost negative words:", [inv_vocab[i] for i in order[:5]])
    print("Most positive words:", [inv_vocab[i] for i in order[-5:]])

    # Try it on new sentences.
    for sentence in ["a wonderful and brilliant film", "boring awful and terrible"]:
        p = predict(bag_of_words(sentence, vocab).reshape(1, -1), w, b)[0]
        print(f'\n"{sentence}"  ->  {"positive" if p > 0 else "negative"}')

    print("\n--- To use the FULL dataset ---")
    print("Download the Stanford Large Movie Review dataset:")
    print("  https://ai.stanford.edu/~amaas/data/sentiment/")
    print("Load the text files, label 1 for pos / -1 for neg, and reuse this exact code.")
    print("For a stronger vectorizer, swap build_vocabulary/bag_of_words for")
    print("sklearn.feature_extraction.text.CountVectorizer.")


if __name__ == "__main__":
    main()
