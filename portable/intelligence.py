"""Offline native tool adapters and persistent hybrid document/graph memory.

No tool is downloaded or started automatically. Paths refer to a user-supplied
portable bundle; optional embedding dependencies are imported only on use.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess


def _file(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Expected a regular file: " + str(path))
    return path


def run_tool(executable, arguments, *, text=None, timeout=300):
    """Execute an explicit local binary without a shell and with a deadline."""
    executable = _file(executable)
    return subprocess.run([str(executable), *map(str, arguments)], input=text,
                          text=True, encoding="utf-8", capture_output=True, timeout=timeout,
                          check=True, env={**os.environ,
                          "PYTHONDONTWRITEBYTECODE": "1",
                          "PYTHONNOUSERSITE": "1"}).stdout


class LocalTools:
    """Adapters for llama-cli, whisper-cli and Piper's documented CLI forms."""
    def __init__(self, manifest):
        self.manifest_path = _file(manifest)
        self.root = self.manifest_path.parent.resolve()
        self.config = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def asset(self, name):
        assets = self.config["assets"]
        if isinstance(assets, list):
            matches = [asset for asset in assets if asset["id"] == name]
            if len(matches) != 1:
                raise ValueError("Expected exactly one asset: " + name)
            relative = "runtime/" + name + "/" + matches[0]["entrypoint"]
            record = {"path": relative,
                      "sha256": self.config["files"][relative]["sha256"]}
        else:
            record = assets[name]
        path = (self.root / record["path"]).resolve(strict=True)
        if self.root not in path.parents or not path.is_file():
            raise ValueError("Asset must be a file inside the portable bundle")
        expected = record.get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Asset requires a SHA-256 digest")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError("Asset digest mismatch: " + name)
        return path

    def generate(self, prompt, tier="scout", max_tokens=256):
        if tier not in ("scout", "general", "deep"):
            raise ValueError("Unknown model tier")
        if not 1 <= max_tokens <= 32768:
            raise ValueError("max_tokens must be between 1 and 32768")
        return run_tool(self.asset("llama"), ["-m", self.asset(tier),
                        "-p", prompt, "-n", max_tokens, "-c", 2048, "-ngl", 0,
                        "--device", "none",
                        "--no-repack", "--flash-attn", "off", "-t", 2, "-tb", 2,
                        "--temp", 0, "--seed", 42, "--no-display-prompt",
                        "--offline", "--single-turn", "--simple-io"])

    def transcribe(self, audio):
        return run_tool(self.asset("whisper"), ["-m", self.asset("whisper_model"),
                        "-f", _file(audio), "-nt"])

    def speak(self, text, output):
        output = Path(output).resolve()
        if output.exists():
            raise ValueError("Refusing to overwrite existing audio")
        piper = self.asset("piper")
        executable, prefix = piper, []
        if piper.suffix == ".py":
            executable, prefix = self.asset("python"), ["-X", "utf8", "-I", "-B", piper]
        run_tool(executable, [*prefix, "--model", self.asset("piper_model"),
                 "--config", self.asset("piper_config"), "--output_file", output], text=text)
        if not output.is_file() or output.stat().st_size < 44:
            raise ValueError("Piper did not produce a WAV file")
        return output


class BGEEmbedder:
    """Local-only bge-small-en-v1.5 using the optional sentence-transformers extra."""
    def __init__(self, model_directory):
        from sentence_transformers import SentenceTransformer
        path = Path(model_directory).resolve(strict=True)
        if not path.is_dir():
            raise ValueError("Embedding model must be a local directory")
        self.model = SentenceTransformer(str(path), local_files_only=True,
                                         trust_remote_code=False)

    def encode(self, text, query=False):
        if query:
            text = "Represent this sentence for searching relevant passages: " + text
        return self.model.encode(text, normalize_embeddings=True).tolist()


def _tokens(text):
    return re.findall(r"\w+", text.casefold())


def _vector(value):
    value = list(value)
    if not value or any(isinstance(x, bool) or not isinstance(x, (float, int))
                        or not math.isfinite(x) for x in value):
        raise ValueError("Embedding must contain finite numbers")
    scale = max(abs(x) for x in value)
    if scale == 0:
        raise ValueError("Embedding must have nonzero norm")
    scaled = [x / scale for x in value]
    norm = math.sqrt(sum(x * x for x in scaled))
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Embedding must have nonzero norm")
    return [x / norm for x in scaled]


class Memory:
    """SQLite document store, BM25/vector rank fusion, and sourced graph edges."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, text TEXT NOT NULL,
                embedding TEXT);
            CREATE TABLE IF NOT EXISTS edges(source TEXT, relation TEXT, target TEXT,
                document TEXT REFERENCES documents(id) ON DELETE CASCADE,
                PRIMARY KEY(source, relation, target, document));
        """)

    def close(self):
        self.db.close()

    def put(self, identifier, text, embedding=None):
        vector = _vector(embedding) if embedding is not None else None
        existing = self.db.execute("SELECT embedding FROM documents WHERE embedding IS NOT NULL LIMIT 1").fetchone()
        if vector and existing and len(vector) != len(json.loads(existing[0])):
            raise ValueError("Embedding dimension mismatch")
        with self.db:
            previous = self.db.execute("SELECT text FROM documents WHERE id=?", (identifier,)).fetchone()
            if previous and previous[0] != text:
                self.db.execute("DELETE FROM edges WHERE document=?", (identifier,))
            self.db.execute("INSERT INTO documents VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text, embedding=excluded.embedding",
                            (identifier, text, json.dumps(vector) if vector else None))

    def relate(self, source, relation, target, document):
        if not all((source, relation, target, document)):
            raise ValueError("Graph edges require source, relation, target and evidence")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO edges VALUES(?,?,?,?)", (source, relation, target, document))

    def neighbors(self, entity):
        return [dict(zip(("source", "relation", "target", "document"), row)) for row in
                self.db.execute("SELECT * FROM edges WHERE source=? OR target=? ORDER BY source,relation,target,document", (entity, entity))]

    def search(self, query, embedding=None, limit=10):
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        rows = self.db.execute("SELECT id,text,embedding FROM documents ORDER BY id").fetchall()
        if not rows:
            return []
        words = [_tokens(row[1]) for row in rows]
        terms = set(_tokens(query))
        average = sum(map(len, words))/len(words) or 1
        lexical = []
        for row, tokens in zip(rows, words):
            score = 0
            for term in terms:
                count = tokens.count(term)
                frequency = sum(term in doc for doc in words)
                idf = math.log(1 + (len(rows)-frequency+0.5)/(frequency+0.5))
                score += idf * count * 2.2/(count + 1.2*(0.25+0.75*len(tokens)/average))
            if score > 0:
                lexical.append((row[0], score))
        rankings = []
        if terms:
            rankings.append(sorted(lexical, key=lambda x: (-x[1], x[0])))
        if embedding is not None:
            vector = _vector(embedding)
            semantic = []
            for identifier, _, stored in rows:
                if stored:
                    stored = json.loads(stored)
                    if len(vector) != len(stored):
                        raise ValueError("Embedding dimension mismatch")
                    semantic.append((identifier, sum(a*b for a,b in zip(vector, stored))))
            rankings.append(sorted(semantic, key=lambda x: (-x[1], x[0])))
        scores = {}
        for ranking in rankings:
            for rank, (identifier, _) in enumerate(ranking, 1):
                scores[identifier] = scores.get(identifier, 0) + 1/(60+rank)
        documents = {row[0]: row[1] for row in rows}
        return [{"id": identifier, "text": documents[identifier], "score": score}
                for identifier, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("prompt")
    generate.add_argument("--tier", choices=("scout", "general", "deep"), default="scout")
    transcribe = commands.add_parser("transcribe")
    transcribe.add_argument("audio")
    speak = commands.add_parser("speak")
    speak.add_argument("text")
    speak.add_argument("output")
    args = parser.parse_args()
    adapter = LocalTools(args.manifest)
    if args.command == "generate":
        print(adapter.generate(args.prompt, args.tier))
    elif args.command == "transcribe":
        print(adapter.transcribe(args.audio))
    else:
        print(adapter.speak(args.text, args.output))


if __name__ == "__main__":
    main()
