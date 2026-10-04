"""사용자에게 줄 번역 TSV — 29KB(UTF-8) 단위로 나누고 자투리는 합친다.
열: 번호 파일 자리 원문 번역. 번호로 work/text/sw_etc.tsv(숫자)·sw_sys.tsv(S…)와 맞춘다."""
import os, sys
LIM = 29 * 1024
HEAD = "#번호\t파일\t자리\t원문\t번역\n"

def rows():
    out = []
    for ln in open("work/text/sw_etc.tsv", encoding="utf-8").read().splitlines()[1:]:
        n, f, s, src, _cnt, _tr = ln.split("\t")
        out.append(f"{n}\t{f}\t{s}\t{src}\t\n")
    for ln in open("work/text/sw_sys.tsv", encoding="utf-8").read().splitlines()[1:]:
        n, f, lst, i, pos, src, _tr = ln.split("\t")
        out.append(f"{n}\t{f}\t{lst}/{i}/{pos}\t{src}\t\n")
    return out

def split(lines):
    chunks, cur, size = [], [], len(HEAD.encode())
    for l in lines:
        b = len(l.encode())
        if cur and size + b > LIM:
            chunks.append(cur); cur, size = [], len(HEAD.encode())
        cur.append(l); size += b
    if cur: chunks.append(cur)
    return chunks

def main(outdir):
    chunks = split(rows())
    os.makedirs(outdir, exist_ok=True)
    for i, c in enumerate(chunks, 1):
        p = os.path.join(outdir, f"sw_{i:03d}.tsv")
        open(p, "w", encoding="utf-8", newline="").write(HEAD + "".join(c))
        print(p, os.path.getsize(p), len(c))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "my files/tsv")
