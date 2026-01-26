"""한글 처리 유틸리티."""

# 한글 초성 목록 (19개)
CHOSUNG = [
    'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ',
    'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
]

# 유니코드 한글 시작점
HANGUL_START = 0xAC00  # '가'
HANGUL_END = 0xD7A3    # '힣'


def extract_chosung(text: str) -> str:
    """
    문자열에서 한글 초성을 추출합니다.

    Args:
        text: 원본 문자열 (예: "삼성전자")

    Returns:
        초성 문자열 (예: "ㅅㅅㅈㅈ")

    Examples:
        >>> extract_chosung("삼성전자")
        'ㅅㅅㅈㅈ'
        >>> extract_chosung("SK하이닉스")
        'SKㅎㅇㄴㅅ'
        >>> extract_chosung("LG에너지솔루션")
        'LGㅇㄴㅈㅅㄹㅅ'
    """
    result = []

    for char in text:
        code = ord(char)

        # 한글 음절인 경우
        if HANGUL_START <= code <= HANGUL_END:
            # 초성 인덱스 계산: (code - 0xAC00) // 588
            # 588 = 21(중성) * 28(종성)
            chosung_index = (code - HANGUL_START) // 588
            result.append(CHOSUNG[chosung_index])
        else:
            # 한글이 아닌 경우 그대로 유지 (알파벳, 숫자 등)
            result.append(char)

    return ''.join(result)


def is_chosung_only(text: str) -> bool:
    """
    문자열이 초성만으로 이루어져 있는지 확인합니다.

    Args:
        text: 확인할 문자열

    Returns:
        초성만으로 이루어져 있으면 True (예: "ㅅㅅㅈㅈ")
    """
    if not text:
        return False

    for char in text:
        # 초성 문자인 경우 OK
        if char in CHOSUNG:
            continue
        # 공백은 허용
        if char == ' ':
            continue
        # 영문/숫자는 허용 (예: "SKㅎㅇㄴㅅ"에서 SK 부분)
        if char.isascii() and char.isalnum():
            continue
        # 그 외 (한글 음절 포함)는 초성이 아님
        return False
    return True


def matches_chosung(text: str, pattern: str) -> bool:
    """
    텍스트가 초성 패턴과 매칭되는지 확인합니다.

    Args:
        text: 원본 텍스트 (예: "삼성전자")
        pattern: 초성 패턴 (예: "ㅅㅅ")

    Returns:
        패턴이 텍스트 초성에 포함되면 True

    Examples:
        >>> matches_chosung("삼성전자", "ㅅㅅ")
        True
        >>> matches_chosung("삼성전자", "ㅈㅈ")
        True
        >>> matches_chosung("삼성전자", "ㅎㅇ")
        False
    """
    text_chosung = extract_chosung(text).upper()
    pattern_upper = pattern.upper()
    return pattern_upper in text_chosung
