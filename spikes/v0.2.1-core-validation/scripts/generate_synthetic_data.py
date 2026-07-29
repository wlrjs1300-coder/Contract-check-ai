"""Generate synthetic employment-contract-like text for v0.2.1 spikes.

This script uses only the Python standard library. It does not download data,
call networks, or use real personal data or real contract text.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path


DEFAULT_SEED = 20260712
DEFAULT_COUNT = 3
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1] / "data" / "generated"
)


NUMBERING_STYLES = ["1.", "1)", "(1)", "제1조", "제 1 조", "①"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate fully synthetic employment contract text files."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic output. Default: {DEFAULT_SEED}",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of documents to generate. Default: {DEFAULT_COUNT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.count < 1:
        raise ValueError("--count must be greater than or equal to 1.")
    if args.count > 100:
        raise ValueError("--count must be 100 or less for local spike safety.")


def clause_number(style: str, index: int) -> str:
    circled = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]
    if style == "1.":
        return f"{index}."
    if style == "1)":
        return f"{index})"
    if style == "(1)":
        return f"({index})"
    if style == "제1조":
        return f"제{index}조"
    if style == "제 1 조":
        return f"제 {index} 조"
    if style == "①":
        return circled[(index - 1) % len(circled)]
    return f"{index}."


def build_document(case_number: int, rng: random.Random) -> str:
    style = rng.choice(NUMBERING_STYLES)
    user_id = f"가상 사용자 {case_number:03d}"
    company_id = f"예시회사 {case_number:03d}"
    address = f"예시시 예시구 예시로 {100 + case_number}"
    email = f"user{case_number:03d}@example.invalid"

    clauses = [
        ("문서 성격", "이 문서는 v0.2.1 스파이크 검증을 위한 완전 합성 텍스트이다."),
        ("당사자", f"근로자 표시는 {user_id}, 회사 표시는 {company_id}로 둔다."),
        ("근무 장소", f"근무 장소 예시는 {address}이며 실제 주소가 아니다."),
        ("연락 수단", f"검증용 이메일 표시는 {email}이며 실제 연락처가 아니다."),
        ("업무", "업무 내용은 예시 업무 A, 예시 업무 B, 예시 문서 정리로 표현한다."),
        ("근무 시간", "근무 시간은 예시 기준으로만 적고 실제 근로조건을 나타내지 않는다."),
        ("보수", "보수 항목은 금액 대신 예시 보수 항목이라는 문구로만 표시한다."),
        ("비밀 유지", "비밀 유지 조항처럼 보이는 문장을 포함하지만 실제 효력은 없다."),
        ("특약", "특약 예시는 조항 분할 경계 확인을 위한 합성 문장이다."),
    ]

    rng.shuffle(clauses)
    selected = clauses[: rng.randint(6, len(clauses))]

    lines = [
        "[실험용 합성 데이터]",
        "이 파일은 실제 계약서가 아니며 법률적으로 유효한 양식이 아니다.",
        "제품 분석 결과가 아니며 실제 개인정보나 실제 계약서 문구를 포함하지 않는다.",
        "",
        f"합성 근로계약서 형식 예시 {case_number:03d}",
        "",
    ]

    if rng.choice([True, False]):
        lines.extend(["머리글: v0.2.1 synthetic spike", ""])

    for index, (title, body) in enumerate(selected, start=1):
        number = clause_number(style, index)
        if rng.choice([True, False]):
            lines.append(f"{number} {title}")
            lines.append(body)
        else:
            lines.append(f"{number} {title} - {body}")
        if rng.choice([True, False]):
            lines.append("")

    if rng.choice([True, False]):
        lines.extend(
            [
                "표 형태 추출 예시",
                "항목 | 내용",
                "역할 | 합성 검증",
                "상태 | 실제 계약 아님",
                "",
            ]
        )

    if rng.choice([True, False]):
        lines.extend(["제목 없는 문단", "이 문단은 조항 번호가 없는 경계 사례이다.", ""])

    lines.extend(
        [
            "부칙",
            "이 부칙은 합성 데이터의 끝부분 경계를 확인하기 위한 문장이다.",
            "",
            "서명란",
            "근로자: 가상 서명",
            "회사: 예시 서명",
        ]
    )

    if rng.choice([True, False]):
        lines.append("바닥글: synthetic document only")

    return "\n".join(lines) + "\n"


def write_documents(seed: int, count: int, output_dir: Path) -> list[Path]:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = [
        output_dir / f"synthetic-employment-contract-{index:03d}.sample.txt"
        for index in range(1, count + 1)
    ]
    existing = [target for target in targets if target.exists()]
    if existing:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing generated file(s): " + names
        )

    written: list[Path] = []
    for index, target in enumerate(targets, start=1):
        text = build_document(index, rng)
        target.write_text(text, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        written = write_documents(args.seed, args.count, args.output_dir)
    except Exception as exc:  # noqa: BLE001 - clear CLI failure message
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"seed: {args.seed}")
    print(f"generated_count: {len(written)}")
    print(f"output_directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
