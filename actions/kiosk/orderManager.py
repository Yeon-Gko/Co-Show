from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import logging
import order_utils
import re


class OrderManager:
    # 주문 관련 정보를 저장할 딕셔너리 초기화
    def __init__(self):
        self.orders = {}  # 음료별 주문 수량을 저장하는 딕셔너리
        self.temperatures = {}  # 음료별 온도를 저장하는 딕셔너리
        self.sizes = {}  # 음료별 사이즈를 저장하는 딕셔너리
        self.additional_option = {}  # 음료별 추가 옵션을 저장하는 딕셔너리
        self.hot_drinks = ["허브티"]  # 항상 핫으로만 제공되는 음료 리스트
        self.ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]  # 항상 아이스로만 제공되는 음료 리스트

    # 커피 추가 메서드
    def add_order(self, drink_type, quantity, temperature=None, size=None, additional_options=None):
        
        drink_type =  order_utils.standardize_drink_name(drink_type)  # 음료 이름 표준화
        
        # 새로운 음료 주문을 추가하거나 기존 주문에 수량을 추가하는 메서드
        if drink_type not in self.orders:
            # 음료 타입이 처음 주문될 경우 초기화
            self.orders[drink_type] = 0
            self.temperatures[drink_type] = []
            self.sizes[drink_type] = []
            self.additional_option[drink_type] = []

        # 음료 타입에 대한 온도, 사이즈, 추가 옵션을 각각 quantity 수만큼 리스트에 추가
        self.orders[drink_type] += quantity
        self.temperatures[drink_type].extend([temperature] * quantity)
        self.sizes[drink_type].extend([size] * quantity)
        self.additional_option[drink_type].extend([additional_options] * quantity)

    # 커피 변경 메서드
    def modify_order(self, old_drink_type, new_drink_type, quantity, temperature=None, size=None, additional_options=None):
        old_drink_type = order_utils.standardize_drink_name(old_drink_type)  # 음료 이름 표준화
        new_drink_type = order_utils.standardize_drink_name(new_drink_type)  # 음료 이름 표준화
        
        # 기존 주문을 새로운 주문으로 수정하는 메서드
        if old_drink_type in self.orders:
            # 기존 음료 주문을 제거
            self.subtract_order(old_drink_type, quantity, temperature, size, additional_options)
        # 새로운 음료 주문을 추가
        self.add_order(new_drink_type, quantity, temperature, size, additional_options)

    # 커피 제거 메서드
    def subtract_order(self, drink_type, quantity, temperature=None, size=None, additional_options=None):
        drink_type = order_utils.standardize_drink_name(drink_type)  # 음료 이름 표준화
        # 주문에서 특정 음료의 수량을 감소시키는 메서드
        if drink_type in self.orders:
            if quantity is None:
                quantity = 1
            # 조건에 맞는 음료의 인덱스를 저장할 리스트
            indices_to_remove = []
            # 조건에 맞는 음료의 인덱스를 찾기(이미 매핑이 된 상태로 디폴트 값을 넣었음)
            for i in range(len(self.temperatures[drink_type])):
                if (self.temperatures[drink_type][i] == temperature) and (self.sizes[drink_type][i] == size) and (self.additional_option[drink_type][i] == additional_options):
                    indices_to_remove.append(i)
                    if len(indices_to_remove) == quantity:
                        break

            if len(indices_to_remove) < quantity:
                # 음료 수량이 부족할 경우 예외 발생 -> 즉, 초과
                raise ValueError(f"{drink_type}의 수량이 충분하지 않습니다.")
            else:
                # 음료 정보에서 해당 인덱스의 항목들을 제거
                for index in reversed(indices_to_remove):
                    del self.temperatures[drink_type][index]
                    del self.sizes[drink_type][index]
                    del self.additional_option[drink_type][index]
                self.orders[drink_type] -= quantity
                # 음료 수량이 0 이하일 경우 해당 음료 정보를 삭제
                if self.orders[drink_type] <= 0:
                    del self.orders[drink_type]
                    del self.temperatures[drink_type]
                    del self.sizes[drink_type]
                    del self.additional_option[drink_type]
        else:
            raise ValueError(f"{drink_type}은(는) 주문에 없습니다.")

    # 커피 추가옵션 추가 메서드
    def add_additional_options(self, drink_type, quantity, temperature, size, current_options, add_additional_options):
        # 음료 이름을 표준화하여 데이터베이스의 일관성과 맞추기
        drink_type = order_utils.standardize_drink_name(drink_type)
        logging.warning(f"추가옵션 추가 실행")  # 추가 옵션 추가 작업 시작을 로그에 기록
        logging.warning(f"{drink_type, quantity, temperature, size, current_options, add_additional_options}")

        if drink_type in self.orders:  # 주어진 음료가 현재 주문에 존재하는지 확인
            indices_to_modify = []  # 수정할 인덱스를 저장할 리스트 초기화

            # add_additional_options가 문자열인지 확인하고, 문자열이면 split 처리
            if isinstance(add_additional_options, str):
                add_additional_options_list = [opt.strip() for opt in add_additional_options.split(",")]
            else:
                add_additional_options_list = [opt.strip() for opt in add_additional_options]

            # current_options도 리스트로 변환
            if isinstance(current_options, str):
                current_options_list = [opt.strip() for opt in current_options.split(",")]
            else:
                current_options_list = [opt.strip() for opt in current_options]

            # 현재 옵션과 추가 옵션 비교 및 처리
            for i in range(len(self.additional_option[drink_type])):  # 모든 주문 항목을 반복
                current_temp = self.temperatures[drink_type][i]  # 현재 항목의 온도 정보 가져오기
                current_size = self.sizes[drink_type][i]  # 현재 항목의 사이즈 정보 가져오기
                existing_options = self.additional_option[drink_type][i].split(", ") if self.additional_option[drink_type][i] else []  # 현재 항목의 옵션 목록 가져오기

                logging.warning(f"현재 옵션: {existing_options}, 현재 온도: {current_temp}, 현재 사이즈: {current_size}")  # 현재 옵션, 온도, 사이즈 로그 기록
                logging.warning(f"추가해야할 옵션: {add_additional_options_list}")  # 추가해야할 옵션 로그 기록
                logging.warning(f"현재 옵션 self: {current_options_list}, 현재 옵션: {existing_options}")

                if current_temp == temperature and current_size == size:
                    if set(current_options_list) == set(existing_options):
                        # 기존 옵션에 새로운 옵션 추가
                        updated_options = list(set(existing_options) | set(add_additional_options_list))
                        self.additional_option[drink_type][i] = ", ".join(updated_options)
                        logging.warning(f"수정된 옵션: {self.additional_option[drink_type][i]}")
                        indices_to_modify.append(i)

                        if len(indices_to_modify) == quantity:
                            logging.warning(f"수정 완료: {indices_to_modify}")
                            break

            if len(indices_to_modify) < quantity:
                raise ValueError(f"{drink_type}의 추가 옵션 수량이 충분하지 않습니다.")
        else:
            raise ValueError(f"{drink_type}은(는) 주문에 없습니다.")

    # 커피 추가옵션 제거 메서드
    def remove_additional_options(self, drink_type, quantity, temperature, size, current_options, last_remove_option):
        drink_type = order_utils.standardize_drink_name(drink_type)  # 음료 이름 표준화
        logging.warning(f"추가옵션 제거 실행")
        logging.warning(f"현재 옵션: {current_options}, 제거 옵션: {last_remove_option}")

        if drink_type in self.orders:
            indices_to_modify = []

            for i in range(len(self.additional_option[drink_type])):
                current_temp = self.temperatures[drink_type][i]
                current_size = self.sizes[drink_type][i]
                current_options_list = self.additional_option[drink_type][i].split(", ") if self.additional_option[drink_type][i] else []

                logging.warning(f"현재 옵션: {current_options_list}, 온도: {current_temp}, 사이즈: {current_size}")

                if current_temp == temperature and current_size == size:
                    if set(current_options_list) == set(current_options):
                        # Remove the specified option
                        updated_options = [opt for opt in current_options_list if opt != last_remove_option]
                        logging.warning(f"제거 후 옵션: {updated_options}")

                        self.additional_option[drink_type][i] = ", ".join(updated_options)
                        indices_to_modify.append(i)
                        if len(indices_to_modify) == quantity:
                            break

            if len(indices_to_modify) < quantity:
                raise ValueError(f"{drink_type}의 추가 옵션 수량이 충분하지 않습니다.")
        else:
            raise ValueError(f"{drink_type}은(는) 주문에 없습니다.")

    # 주문 취소 메서드
    def cancel_order(self):
        # 현재 모든 주문을 취소하고 초기화하는 메서드
        canceled_orders = self.orders.copy()  # 기존 주문을 백업
        self.orders = {}
        self.temperatures = {}
        self.sizes = {}
        self.additional_option = {}
        return canceled_orders  # 취소된 주문 반환

    # 주문 내역 초기화 메서드
    def clear_order(self):
        # 현재 주문을 초기화하는 메서드
        self.orders.clear()
        self.temperatures.clear()
        self.sizes.clear()
        self.additional_option.clear()

    # 주문 내역 반환 메서드
    def get_orders(self):
        # 현재 주문 정보를 반환하는 메서드
        return self.orders

    # 주문 확인 후 출력 메서드
    def get_order_summary(self):
        # 현재 주문 정보를 생성하여 반환하는 메서드
        summary = []
        # self.orders의 모든 음료 항목(음료 종류와 수량)에 대해 반복해 각 음료의 온도, 사이즈, 추가 옵션 정보를 가져옵니다.
        for drink, quantity in self.orders.items():
            temperatures = self.temperatures.get(drink, [None] * quantity)
            sizes = self.sizes.get(drink, [None] * quantity)
            options = self.additional_option.get(drink, [None] * quantity)

            drink_summary = {}
            for i in range(quantity):
                temp = temperatures[i] if i < len(temperatures) else None
                size = sizes[i] if i < len(sizes) else None
                option = options[i] if i < len(options) else None
                key = (temp, size, option)
                if key in drink_summary:
                    drink_summary[key] += 1
                else:
                    drink_summary[key] = 1

            for (temp, size, option), count in drink_summary.items():
                summary_item = f"{drink}"
                if size:
                    summary_item = f"{summary_item} {size}"
                if temp:
                    summary_item = f"{temp} {summary_item}"
                if option:
                    # 여러 옵션을 "추가"라는 단어와 함께 출력
                    options_list = option.split(", ")
                    options_str = ", ".join(options_list) + " 추가"
                    summary_item = f"{summary_item} {options_str}"
                summary_item = f"{summary_item} {order_utils.number_to_korean(count)} 잔"
                summary.append(summary_item.strip())
        return ", ".join(summary)

order_manager = OrderManager()  # OrderManager 인스턴스 생성
