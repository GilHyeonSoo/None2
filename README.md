# UAM Handover Project

이 저장소는 UAM 핸드오버 시뮬레이션, CSV 분석, 논문용 표·그림 생성, 제출 문서 조합까지를 한 폴더 안에서 관리한다.

## 폴더 구조

```text
논문/
├── README.md
├── data/
│   └── legacy/
├── docs/
│   ├── guides/
│   └── references/
├── manuscript/
│   ├── drafts/
│   └── submission/
├── results/
│   ├── raw/
│   ├── analysis/
│   ├── tables/
│   └── figures/
└── scripts/
```

## 주요 위치

- 작업 지침: [`/Users/apple/Desktop/논문/docs/guides/prompt.md`](/Users/apple/Desktop/논문/docs/guides/prompt.md)
- 데이터 해석 지침: [`/Users/apple/Desktop/논문/docs/guides/DataRead.md`](/Users/apple/Desktop/논문/docs/guides/DataRead.md)
- 관련 의견 메모: [`/Users/apple/Desktop/논문/docs/guides/DataRead_opinion.txt`](/Users/apple/Desktop/논문/docs/guides/DataRead_opinion.txt)
- 시뮬레이션 시나리오 설명: [`/Users/apple/Desktop/논문/docs/guides/simulation_scenario.md`](/Users/apple/Desktop/논문/docs/guides/simulation_scenario.md)
- 참조 논문 PDF: [`/Users/apple/Desktop/논문/docs/references/related_works`](/Users/apple/Desktop/논문/docs/references/related_works)
- 문체 예시: [`/Users/apple/Desktop/논문/docs/references/examples`](/Users/apple/Desktop/논문/docs/references/examples)
- 초안 논문: [`/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt`](/Users/apple/Desktop/논문/manuscript/drafts/UAM_Intro_Draft.txt)
- 제출용 원문: [`/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.txt`](/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.txt)
- 제출용 문서: [`/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.docx`](/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.docx), [`/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.pdf`](/Users/apple/Desktop/논문/manuscript/submission/UAM_Submission_Ready.pdf)

## 결과물 위치

- 원시 스윕 결과: [`/Users/apple/Desktop/논문/results/raw`](/Users/apple/Desktop/논문/results/raw)
- 분석 CSV: [`/Users/apple/Desktop/논문/results/analysis`](/Users/apple/Desktop/논문/results/analysis)
- 논문용 표: [`/Users/apple/Desktop/논문/results/tables`](/Users/apple/Desktop/논문/results/tables)
- 탐색용 그림: [`/Users/apple/Desktop/논문/results/figures/exploratory`](/Users/apple/Desktop/논문/results/figures/exploratory)
- 논문용 그림: [`/Users/apple/Desktop/논문/results/figures/paper`](/Users/apple/Desktop/논문/results/figures/paper)

## 실행 순서

1. 전체 시뮬레이션

```bash
python3 /Users/apple/Desktop/논문/scripts/run_simulation_sweep.py
```

2. CSV 분석

```bash
python3 /Users/apple/Desktop/논문/scripts/analyze_simulation_csv.py
```

3. 논문용 표·그림 생성

```bash
python3 /Users/apple/Desktop/논문/scripts/build_paper_outputs.py
```

4. 제출용 문서 생성

```bash
python3 /Users/apple/Desktop/논문/scripts/build_submission_doc.py
```

## 정리 원칙

- `results/raw`: 재분석 가능한 원시 결과만 보관
- `results/analysis`: CSV 기반 추가 분석 결과만 보관
- `results/tables`, `results/figures/paper`: 최종 논문 산출물
- `data/legacy`: 과거 실험 파일과 예전 그래프 보관
- 루트에는 진입점 파일과 상위 디렉토리만 남긴다
