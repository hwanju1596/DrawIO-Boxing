# Draw.io 개체 하이라이트 스크립트

이 파이썬 스크립트는 Draw.io 파일(.drawio) 내의 특정 텍스트나 도형을 찾아 그 주위에 노란색 하이라이트 박스를 자동으로 추가합니다.

## 기능

- **텍스트 하이라이트**: 지정된 텍스트 또는 접두사(prefix)로 시작하는 모든 텍스트를 찾아 하이라이트합니다.
- **도형 하이라이트**: 기준 도형과 형태가 유사한 모든 원(circle)을 찾아 하이라이트합니다. 크기가 달라도 찾아낼 수 있습니다.

## 요구 사항

- Python 3
- `numpy` 라이브러리
  ```bash
  pip install numpy
  ```

## 사용법

기본적인 명령어 구조는 다음과 같습니다:

```bash
python highlight_drawio.py <입력 파일> <출력 파일> [모드] [옵션]
```

### 1. 도형 하이라이트 (`--shape circle`)

도면 파일 내에서 기준 원과 유사한 모든 원을 찾아 하이라이트합니다.

**기본 명령어:**

```bash
python highlight_drawio.py <입력 파일> <출력 파일> --shape circle
```

**옵션:**

- `--ref_prefix <접두사>`: 원의 기준이 될 도형의 ID 접두사를 지정합니다. (기본값: `AR_G_2_`)
- `--tolerance <숫자>`: 도형의 유사성을 판단하는 허용 오차 값입니다. 값이 클수록 더 너그럽게 판단합니다. (기본값: `0.5`)
- `--padding <숫자>`: 하이라이트 박스의 여백(테두리 두께)입니다. (기본값: `10`)

**예시:**

- 기본 설정으로 원 찾기:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --shape circle
  ```
- 하이라이트 박스 여백을 20으로 늘리기:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --shape circle --padding 20
  ```
- `AR_G_3_` 도형을 기준으로, 허용 오차 `1.0`으로 찾기:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --shape circle --ref_prefix AR_G_3_ --tolerance 1.0
  ```

### 2. 텍스트 하이라이트 (`--text`)

지정한 텍스트 또는 텍스트 목록으로 시작하는 모든 요소를 하이라이트합니다.

**기본 명령어:**

```bash
python highlight_drawio.py <입력 파일> <출력 파일> --text "<검색어>"
```

**옵션:**

- `--padding <숫자>`: 하이라이트 박스의 여백입니다. (기본값: `10`)

**예시:**

- "CM-"으로 시작하는 모든 텍스트 하이라이트:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --text "CM-"
  ```
- 쉼표로 여러 접두사 지정 ("CM-", "ELV-"):
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --text "CM-,ELV-"
  ```
- 여백을 15로 지정하여 하이라이트:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --text "CM-" --padding 15
  ```

### 3. 구성 파일(`highlight_config.json`)을 이용한 텍스트 하이라이트 (`--config`)

여러 텍스트 접두사를 파일에 미리 정의해두고 한 번에 실행할 수 있습니다.

**`highlight_config.json` 파일 예시:**

```json
{
  "text_prefixes": ["CM-", "AR_G_", "ELV-"]
}
```

**기본 명령어:**

```bash
python highlight_drawio.py <입력 파일> <출력 파일> --config <설정 파일 경로>
```

**옵션:**

- `--padding <숫자>`: 하이라이트 박스의 여백입니다. (기본값: `10`)

**예시:**

- `highlight_config.json` 파일을 사용하여 하이라이트 실행:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --config highlight_config.json
  ```
- 구성 파일을 사용하며 여백을 20으로 지정:
  ```bash
  python highlight_drawio.py "input.drawio" "output.drawio" --config highlight_config.json --padding 20
  ```
