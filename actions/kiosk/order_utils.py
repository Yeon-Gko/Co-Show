import re


def korean_to_number(korean: str) -> int:
    # 한국어 수량을 숫자로 변환하는 메서드
    # dictionary.get(key, default), 딕셔너리에서 :의 왼쪽은 키값(key) 오른쪽은 값(value)이다
    korean_number_map = {
        "한": 1,
        "두": 2,
        "세": 3,
        "네": 4,
        "다섯": 5,
        "여섯": 6,
        "일곱": 7,
        "여덟": 8,
        "아홉": 9,
        "열": 10
    }
    return korean_number_map.get(korean, 1)  # korean 문자열이 사전에 존재하지 않으면 기본값으로 1을 반환

# 숫자를 한국어 수량으로 변환하는 메서드
def number_to_korean(number: int) -> str:
    number_korean_map = {
        1: "한",
        2: "두",
        3: "세",
        4: "네",
        5: "다섯",
        6: "여섯",
        7: "일곱",
        8: "여덟",
        9: "아홉",
        10: "열"
    }
    return number_korean_map.get(number, str(number))  # 기본값으로 숫자 문자열을 반환

# 음료 종류 및 띄어쓰기 표준화 메서드
def standardize_drink_name(name):
    # 음료 이름 변형을 표준 이름으로 매핑하는 사전
    drink_name_map = {
        "카페라테": "카페라떼",
        "카페라뗴": "카페라떼",
        "레모네이드" : "레몬에이드",
        "카라멜마키아또" : "카라멜마끼아또",
        "아보카도" : "아포카토",
        "키즈스" : "키위주스",
        "초콜릿" : "초콜릿라떼",
        "초콜릿대" : "초콜릿라떼",
        "바닐라떼" : "바닐라라떼",
        "카라멜막혔더" : "카라멜마끼아또",
        "복숭아ost" : "복숭아아이스티",
        "말자라때" : "말차라떼",
        "바닐라레떼" : "바닐라라떼",
        "아포가토" : "아포카토",
        "복숭아아이스크림" : "복숭아아이스티",
        "허벅지" : "허브티",
        "에스페로" : "에스프레소",
        "다기스무디" : "딸기스무디",
        "망고스머리" : "망고스무디",
        "토마토소스" : "토마토주스",
        "망고스뮤비" : "망고스무디",
        "쿠킹크림" : "쿠키앤크림",
        "쿠킹그림" : "쿠키앤크림",
        "쿠앤크" : "쿠키앤크림",
        "카페북한" : "카페모카",
        "tv스투스" : "키위주스",
        "Tv스투스" : "키위주스",
        "TV스투스" : "키위주스",
        "말잘할때" : "말차라떼",
        "허버트" : "허브티",
        "tv쥬스" : "키위주스",
        "Tv쥬스" : "키위주스",
        "TV쥬스" : "키위주스",
        "아프리카" : "아포카토",
        "마찰할때" : "말차라떼",
        "말찾았대" : "말차라떼",
        "라벨마끼아또" : "카라멜마끼아또",
        "카메라맡기어도" : "카라멜마끼아또",
        "복숭아st" : "복숭아아이스티",
        "복숭아St" : "복숭아아이스티",
        "복숭아ST" : "복숭아아이스티",
        "복숭아에스티" : "복숭아아이스티",
        "복숭아하이스틸" : "복숭아아이스티",
        "호텔" : "허브티",
        "말잘했다" : "말차라떼",
        "카프치노" : "카푸치노",
        "카라멜마끼야또" : "카라멜마끼아또",
        "라떼" : "카페라떼",
        "라뗴" : "카페라떼",
        "라때" : "카페라떼"
    }

    # 공백과 쉼표 제거
    # re.sub는 (패턴, 교체할 값, 검색할 대상 문자열, 교체할 최대횟수(선택), 동작 수정 플래그(선택)) 으로 동작한다.
    standardized_name = re.sub(r'[\s,]+', '', name)

    # 매핑 사전을 사용하여 표준 이름으로 변환
    if standardized_name in drink_name_map:
        return drink_name_map[standardized_name]
    else:
        return standardized_name

# 온도를 표준화하는 메서드
def standardize_temperature(value):
    if value in ["차갑게", "시원하게", "아이스", "차가운", "시원한"]:
        return "아이스"
    elif value in ["뜨겁게", "따뜻하게", "핫", "뜨거운", "따뜻한", "뜨뜻한", "하수", "hot"]:
        return "핫"
    return value

# 잔 수를 표준화하는 메서드
def standardize_quantity(value):
    if value in ["한", "앉", "안", "환", "완", "라", "하나"]:
        return "한"
    elif value in ["두", "도", "투"]:
        return "두"
    elif value in ["세", "재", "대"]:
        return "세"
    elif value in ["네", "내"]:
        return "네"
    elif value in ["다섯", "das"]:
        return "다섯"
    elif value in ["여섯"]:
        return "여섯"
    elif value in ["일곱"]:
        return "일곱"
    elif value in ["여덟"]:
        return "여덟"
    elif value in ["아홉"]:
        return "아홉"
    elif value in ["열"]:
        return "열"
    return value

# 사이즈를 표준화하는 메서드
def standardize_size(value):
    if value in ["미디움", "보통", "중간", "기본", "톨", "비디오", "토"]:
        return "미디움"
    elif value in ["라지", "큰", "크게", "라의", "라디오", "라디"]:
        return "라지"
    elif value in ["엑스라지", "엑스라이즈", "제1 큰", "가장 큰", "제1 크게", "맥시멈"]:
        return "엑스라지"
    return value

# 추가옵션를 표준화하는 메서드
def standardize_option(value):
    if value in ["샤츠", "셔츠", "사추", "샤타나", "4추가"]:
        return "샷"
    elif value in ["카라멜실업", "실룩실룩", "가라멜시럽", "카라멜시로"]:
        return "카라멜시럽"
    elif value in ["바닐라실업"]:
        return "바닐라시럽"
    elif value in ["비비크림"]:
        return "휘핑크림"
    return value

# 테이크아웃을 표준화하는 메서드
def standardize_take(value):
    if value in ["테이크아웃", "들고", "가져", "먹을", "마실", "아니요"]:
        return "포장"
    elif value in ["먹고", "여기", "이곳", "네"]:
        return "매장"
    return value

# 커피의 종류가 정해지지 않으면 오류 발생 메서드
def raise_missing_attribute_error(drinks):
    if not drinks:
        raise ValueError("정확한 음료의 종류를 말씀하여주세요.")
