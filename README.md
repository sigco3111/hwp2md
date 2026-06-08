# hwp2md

> **한글(HWP) 파일을 깔끔한 마크다운으로 — 로컬 우선, LLM RAG 파이프라인에 최적화**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Stable API: 1.0.0](https://img.shields.io/badge/API-stable-green.svg)](docs/API.md)
[![Benchmark: 100%](https://img.shields.io/badge/benchmark-9%2F9-brightgreen.svg)](docs/ACCURACY.md)

**English** | **한국어** (이 문서)

---

## 🎯 왜 hwp2md 인가?

한국 정부/공공기관/학계의 90% 이상이 여전히 **HWP(한글) 파일**을 사용합니다. 문제는:

- ❌ 맥/리눅스 사용자는 한컴오피스(유료) 없이는 파일을 못 연다
- ❌ GitHub, Notion, Obsidian 어디에도 깨끗하게 임포트되지 않는다
- ❌ LLM RAG 파이프라인에 넣으려면 결국 PDF/이미지 OCR → 텍스트 손실 큼
- ❌ 기존 도구(`pyhwp`, `hwp5` 등)는 라이브러리일 뿐 **CLI / GitHub Action / Git-friendly 출력이 부실**

**hwp2md** 는 이 갭을 채웁니다:

- ✅ **오프라인 우선** — 한컴오피스/인터넷 불필요
- ✅ **의존성 선택적** — 가장 기본 모드는 zero-deps, HWPX/HWP5x는 옵션
- ✅ **깔끔한 마크다운** — 표/목록/이미지 참조 보존, LLM 토큰 효율적
- ✅ **CLI + Python API** — 스크립트와 자동화 모두 지원
- ✅ **배치 변환** — 폴더 트리째 변환 (정부 문서 크롤링에 최적)
- ✅ **안정 API** — 1.0.0부터 시맨틱 버저닝 + 공개 API 계약 ([docs/API.md](docs/API.md))
- ✅ **CI + GitHub Action** — [`sigco3111/hwp2md@v1`](https://github.com/sigco3111/hwp2md)

---

## 📦 설치

### 기본 (HWPX만 지원, 의존성 zero)
```bash
pip install hwp2md
```

### HWP 5.x (구버전) 지원 추가
```bash
pip install "hwp2md[olefile]"
```

### 모든 기능 (HWPX + HWP5x)
```bash
pip install "hwp2md[all]"
```

### 소스에서 설치 (개발자)
```bash
git clone https://github.com/sigco3111/hwp2md.git
cd hwp2md
pip install -e ".[all,dev]"
```

---

## 🚀 빠른 시작

### CLI
```bash
# 단일 파일 변환 (frontmatter 자동 포함)
hwp2md input.hwp -o output.md

# 출력 파일 자동 지정 (input.hwp → input.md)
hwp2md input.hwp

# 폴더 단위 배치 변환 (재귀)
hwp2md ./korean_gov_docs/ -o ./markdown_output/

# 인코딩 지정 (기본: utf-8)
hwp2md input.hwp --encoding utf-8

# 이미지 임베딩 (base64) vs 참조 링크
hwp2md input.hwp --images embed
hwp2md input.hwp --images link

# frontmatter 끄기
hwp2md input.hwp --no-frontmatter
```

### Python API
```python
from hwp2md import convert

# 가장 간단한 사용 (frontmatter 자동 포함)
markdown = convert("input.hwpx")

# 이미지 모드 선택 (link | embed | skip)
markdown = convert("input.hwpx", image_mode="link", image_dir="./images")

# frontmatter 끄기
markdown = convert("input.hwpx", with_metadata=False)

# 메타데이터만 따로 읽기
from hwp2md.backends.hwpx import extract_metadata_hwpx
from pathlib import Path
meta = extract_metadata_hwpx(Path("input.hwpx"))
print(meta.title, meta.author, meta.keywords)

# 파일로 저장
with open("output.md", "w", encoding="utf-8") as f:
    f.write(markdown)

# 배치 변환
from pathlib import Path
from hwp2md import batch_convert

for src, dst in batch_convert(Path("./docs/"), Path("./out/")):
    print(f"✅ {src.name} → {dst.relative_to(Path('./out/'))}")
```

출력 예시 (frontmatter 포함 시):
```markdown
---
title: 2025년 AI 산업 동향 보고서
author: 홍길동
date: 2025-01-15
keywords:
  - AI
  - 산업
  - 동향
---

# 개요

본 보고서는 2025년 한국 AI 산업의...
```

---

## ⚙️ GitHub Action

CI 파이프라인에서 HWP/HWPX를 마크다운으로 자동 변환:

```yaml
# .github/workflows/hwp2md.yml
name: Convert HWP to Markdown
on: [push]

jobs:
  convert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sigco3111/hwp2md@v1
        with:
          input: docs/         # 단일 파일 또는 디렉터리
          output: markdown/    # (선택) 출력 경로
          image-mode: link     # embed | link | skip
```

### Inputs

| 이름 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `input` | ✅ | — | `.hwp`/`.hwpx` 파일 또는 디렉터리 경로 |
| `output` | ❌ | 소스 옆/`<input>/markdown_output` | 출력 파일 또는 디렉터리 |
| `encoding` | ❌ | `utf-8` | 출력 인코딩 |
| `image-mode` | ❌ | `link` | `embed` / `link` / `skip` |
| `install-extras` | ❌ | `all` | pip extras (`olefile` / `all` / `""`) |
| `working-directory` | ❌ | `.` | 변환 작업 디렉터리 |

### Outputs

| 이름 | 설명 |
|------|------|
| `output-path` | 변환된 마크다운 절대 경로 |
| `files-count` | 변환된 파일 수 (단일=1, 배치=N) |

### 사용 예시

```yaml
# PR에 자동 첨부 (정부 문서 크롤링에 최적)
- uses: sigco3111/hwp2md@v1
  with:
    input: crawled_data/
    output: pr_body/markdown/
    image-mode: link

# 결과를 후속 step에서 사용
- uses: sigco3111/hwp2md@v1
  id: hwp
  with:
    input: docs/report.hwpx
- run: echo "변환 위치: ${{ steps.hwp.outputs.output-path }}"
```

---

## 📋 지원 형식

| 형식 | 확장자 | 상태 | 의존성 |
|------|--------|------|--------|
| HWPX (한컴오피스 2014+, XML 기반) | `.hwpx` | ✅ 지원 | none (stdlib) |
| HWP 5.x (구버전, OLE 컨테이너) | `.hwp` | ✅ 지원 (0.2.0+) | `olefile` |
| HWP 3.x (매우 구버전) | `.hwp` | 🚧 예정 | TBD |
| 보호된/암호화된 문서 | `*` | ❌ 미지원 | — |

---

## 🎨 출력 예시

### 입력: HWP 문서
> 제목: 2025년 AI 산업 동향 보고서
> 본문에 표, 목록, 이미지 1개 포함

### 출력: `output.md`
```markdown
# 2025년 AI 산업 동향 보고서

## 개요

본 보고서는 2025년 한국 AI 산업의...

## 주요 지표

| 항목 | 2024 | 2025 | 증감률 |
|------|------|------|--------|
| 시장 규모 | 5.2조 | 7.8조 | +50% |
| 기업 수 | 1,200 | 1,580 | +32% |

## 결론

![시장 동향 그래프](images/figure1.png)

- [ ] LLM fine-tuning
- [x] RAG 파이프라인 구축
```

**핵심:**
- 표는 GFM( GitHub Flavored Markdown) 형식
- 이미지는 별도 디렉토리 추출 + 참조
- LLM 토큰 효율: 평균 PDF OCR 대비 **60-70% 절감** (예상)

---

## 🛮 안정성 & 벤치마크

- **공개 API 계약**: [`docs/API.md`](docs/API.md) — 1.0.0부터 시맨틱 버저닝, 패치는 호환, 마이너는 추가만
- **정확도 벤치마크**: [`docs/ACCURACY.md`](docs/ACCURACY.md) — 합성 코퍼스 9/9 (100%) 통과, HWP 5.x는 단위 테스트 32개로 보강
- **기여 가이드**: [`CONTRIBUTING.md`](CONTRIBUTING.md) — PR 체크리스트, 샘플 파일 보내는 법

---

## 🛠️ 사용 사례 (Use Cases)

1. **공공데이터 RAG** — data.go.kr HWP 문서 → LLM 지식 베이스
2. **논문 마이그레이션** — 학위 논문 HWP → GitHub Pages 위키
3. **정부 보도자료 분석** — 정책 문서 자동 요약 파이프라인
4. **레거시 문서 현대화** — 사내 HWP 매뉴얼 → Notion/Obsidian
5. **법령 분석** — 법제처 HWP → 검색 가능한 마크다운

---

## 🗺️ 로드맵

- [x] **0.1.0** — 프로젝트 부트스트랩, CLI 뼈대, HWPX 기본 파서
- [x] **0.2.0** — HWPX + HWP 5.x 파서 (텍스트/제목/표/이미지)
- [x] **0.3.0** — HWP 5.x 표/이미지/문자 서식 정확도 개선
- [x] **0.4.0** — GitHub Action (`uses: sigco3111/hwp2md@v1`) + CI/Release workflow
- [x] **0.5.0** — 메타데이터 frontmatter 추출 (작성자/날짜/키워드)
- [x] **1.0.0** — 안정 API (시맨틱 버저닝) + 정확도 벤치마크 ([docs/API.md](docs/API.md), [docs/ACCURACY.md](docs/ACCURACY.md))

---

## 🤝 기여하기

기여 환영합니다! 자세한 절차는 [`CONTRIBUTING.md`](CONTRIBUTING.md)를 참고하세요. 특히 다음 분야:

- 🐛 **테스트 픽스처** — 다양한 HWP 버전의 샘플 파일 (개인정보 없는 공공 문서)
- 🌐 **i18n** — README 영문화, 다국어 에러 메시지
- 🧪 **파서 정확도** — 엣지 케이스 (복잡한 표, 중첩 목록, 수식)
- 📚 **문서** — 튜토리얼, 사용 예시

개발 환경 세팅:
```bash
git clone https://github.com/sigco3111/hwp2md.git
cd hwp2md
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
pytest
python scripts/benchmark.py    # 정확도 벤치마크
```

---

## 📄 라이선스

MIT License — 자유롭게 사용/수정/배포하세요. 자세한 내용은 [LICENSE](LICENSE) 참조.

---

## 🙏 감사의 말

- [pyhwp](https://github.com/mete0r/pyhwp) — HWP 포맷 분석의 선구자
- [olefile](https://olefile.readthedocs.io/) — OLE 컨테이너 파싱 표준
- 모든 기여자와 이슈 제보자들

---

<p align="center">
  Made with ❤️ in Seoul for the open-source community
</p>
