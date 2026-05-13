import random
import sys
import os
import shelve
import re

# Support for English and Turkish characters
WORD_PATTERN = re.compile(r'^[a-züğışçöâîûı]+$')

# ── File Paths ──
DATA_FILE = "data.txt"
MEMORY_DB = "memory"          # Generates memory.db / .dir / .bak depending on OS
CHUNK_SIZE = 50_000           # Progress update interval

# ══════════════════════════════════════════════════════════════
#  MARKOV AI CLASS
# ══════════════════════════════════════════════════════════════
class DayiAI:
    """
    Disk-backed Markov Chain (Trigram + Bigram fallback).
    Uses Python 'shelve' for memory management — RAM friendly.
    """

    def __init__(self):
        self._db = None
        self._open_db()

    def _open_db(self):
        if self._db is None:
            self._db = shelve.open(MEMORY_DB, flag="c", writeback=False)

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    @staticmethod
    def _tri_key(k1: str, k2: str) -> str:
        return f"t\x00{k1}\x00{k2}"

    @staticmethod
    def _bi_key(k: str) -> str:
        return f"b\x00{k}"

    @staticmethod
    def _is_valid_word(word: str) -> bool:
        """Filter out non-alphabetical or broken words."""
        return bool(WORD_PATTERN.match(word.lower()))

    def _add_entry(self, key: str, value: str):
        """Append value to the list stored in shelve."""
        current = self._db.get(key, [])
        current.append(value)
        self._db[key] = current

    # ──────────────────────────────────────────
    # Training (Line by line, RAM efficient)
    # ──────────────────────────────────────────
    def train(self, file_path: str = DATA_FILE):
        if not os.path.exists(file_path):
            print(f"[ERROR] {file_path} not found!")
            sys.exit(1)

        size_mb = os.path.getsize(file_path) / 1_048_576
        print(f"[Training started — {size_mb:.1f} MB, please be patient... 😅]")

        total_words = 0
        previous_words: list = []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                words = line.lower().split()
                if not words:
                    continue

                # Maintain connection between lines
                window = previous_words + words

                for i in range(len(window) - 1):
                    self._add_entry(self._bi_key(window[i]), window[i + 1])

                for i in range(len(window) - 2):
                    self._add_entry(self._tri_key(window[i], window[i + 1]), window[i + 2])

                previous_words = words[-2:] if len(words) >= 2 else words
                total_words += len(words)

                if line_no % CHUNK_SIZE == 0:
                    print(f"  → {line_no:,} lines / {total_words:,} words processed...")

        print(f"[Training complete ✓ — Total {total_words:,} words]")
        print(f"[Memory saved to '{MEMORY_DB}' database ✓]")

    # ──────────────────────────────────────────
    # Smart Starting Point
    # ──────────────────────────────────────────
    def _get_best_start(self, words: list):
        for i in range(len(words) - 1):
            k = self._tri_key(words[i], words[i + 1])
            if k in self._db:
                return (words[i], words[i + 1])

        for k in words:
            if self._bi_key(k) in self._db:
                return k

        return None

    # ──────────────────────────────────────────
    # Response Generation
    # ──────────────────────────────────────────
    def generate_response(self, query: str, length: int = 15) -> str:
        words = query.lower().split()
        if not words:
            return "Say something! 🙂"

        start = self._get_best_start(words)

        # ── Trigram path ──
        if isinstance(start, tuple):
            k1, k2 = start
            sentence = [k1, k2]
            for _ in range(length):
                options = self._db.get(self._tri_key(k1, k2))
                if not options:
                    break
                
                next_word = None
                for _ in range(10):
                    candidate = random.choice(options)
                    if self._is_valid_word(candidate):
                        next_word = candidate
                        break
                
                if not next_word:
                    break
                sentence.append(next_word)
                k1, k2 = k2, next_word
            return " ".join(sentence).capitalize()

        # ── Bigram fallback ──
        if isinstance(start, str):
            sentence = [start]
            current = start
            for _ in range(length):
                options = self._db.get(self._bi_key(current))
                if not options:
                    break
                
                next_word = None
                for _ in range(10):
                    candidate = random.choice(options)
                    if self._is_valid_word(candidate):
                        next_word = candidate
                        break
                
                if not next_word:
                    break
                sentence.append(next_word)
                current = next_word
            return " ".join(sentence).capitalize()

        return "I haven't learned about that yet, I need more data 🤷"


# ══════════════════════════════════════════════════════════════
#  MAIN PROGRAM
# ══════════════════════════════════════════════════════════════
def main():
    ai = DayiAI()

    db_empty = len(ai._db) == 0
    data_exists = os.path.exists(DATA_FILE)

    if db_empty and not data_exists:
        print(f"Error: Neither '{DATA_FILE}' nor '{MEMORY_DB}' found!")
        ai.close()
        sys.exit(1)

    if db_empty and data_exists:
        # First run — Train the model
        ai.train(DATA_FILE)
    elif not db_empty and data_exists:
        # DB is already populated
        print(f"[Existing memory found ({MEMORY_DB}) — Loading directly]")
        print("[To retrain, delete memory files and run again]")

    print("\n╔════════════════════════════════════╗")
    print("║      Dayi AI Terminal Interface    ║")
    print("║      Type 'exit' to quit           ║")
    print("╚════════════════════════════════════╝\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() == "exit":
                print("Goodbye!")
                break

            print("AI:", ai.generate_response(user_input))
    finally:
        ai.close()


if __name__ == "__main__":
    main()
