from .drink_constants import DrinkConstants
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
import logging
import re

# 로거 설정
logging.basicConfig(level=logging.DEBUG)

# 현재 주문 목록을 저장
class OrderManager:
    # 주문 관련 정보를 저장할 딕셔너리 초기화
    def __init__(self):
        self.orders = {}  # 음료별 주문 수량을 저장하는 딕셔너리
        self.temperatures = {}  # 음료별 온도를 저장하는 딕셔너리
        self.sizes = {}  # 음료별 사이즈를 저장하는 딕셔너리
        self.additional_option = {}  # 음료별 추가 옵션을 저장하는 딕셔너리
        self.hot_drinks = ["허브티"]  # 항상 핫으로만 제공되는 음료 리스트
        self.ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]  # 항상 아이스로만 제공되는 음료 리스트
        self.can_add_shot = ["샷", "카라멜시럽"]
        self.don_add_shot = ["휘핑크림"]
    
    # 커피 추가 메서드
    def add_order(self, drink_type, quantity, temperature=None, size=None, additional_options=None):
        logging.warning(drink_type)
        drink_type = standardize_drink_name(drink_type)  # 음료 이름 표준화
        
        # 새로운 음료 주문을 추가하거나 기존 주문에 수량을 추가하는 메서드
        if drink_type not in self.orders:
            # 음료 타입이 처음 주문될 경우 초기화
            self.orders[drink_type] = 0
            self.temperatures[drink_type] = []
            self.sizes[drink_type] = []
            self.additional_option[drink_type] = []
        if drink_type == "복숭아아이스티" and additional_options and "샷" in additional_options:
            # "샷" 중복 제거
            options_list = additional_options.split(", ") if isinstance(additional_options, str) else additional_options
            options_list = list(dict.fromkeys(options_list))  # 중복 제거
            additional_options = ", ".join(options_list) if options_list else None
            

        # 음료 타입에 대한 온도, 사이즈, 추가 옵션을 각각 quantity 수만큼 리스트에 추가
        self.orders[drink_type] += quantity
        self.temperatures[drink_type].extend([temperature] * quantity)
        self.sizes[drink_type].extend([size] * quantity)
        self.additional_option[drink_type].extend([additional_options] * quantity)

    # 커피 변경 메서드
    def modify_order(self, old_drink_type, new_drink_type, quantity, temperature=None, size=None, additional_options=None):
        old_drink_type = standardize_drink_name(old_drink_type)  # 음료 이름 표준화
        new_drink_type = standardize_drink_name(new_drink_type)  # 음료 이름 표준화
        
        # 기존 주문을 새로운 주문으로 수정하는 메서드
        if old_drink_type in self.orders:
            # 기존 음료 주문을 제거
            self.subtract_order(old_drink_type, quantity, temperature, size, additional_options)
        # 새로운 음료 주문을 추가
        self.add_order(new_drink_type, quantity, temperature, size, additional_options)

    # 커피 제거 메서드
    def subtract_order(self, drink_type, quantity, temperature=None, size=None, additional_options=None):
        drink_type = standardize_drink_name(drink_type)  # 음료 이름 표준화
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
        drink_type = standardize_drink_name(drink_type)
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
                self.add_order(drink_type,quantity,temperature,size,add_additional_options)
                #raise ValueError(f"{drink_type}의 추가 옵션 수량이 충분하지 않습니다.")
        else:
            self.add_order(drink_type,quantity,temperature,size,add_additional_options)
            #raise ValueError(f"{drink_type}은(는) 주문에 없습니다.")

    # 커피 추가옵션 제거 메서드
    def remove_additional_options(self, drink_type, quantity, temperature, size, current_options, last_remove_option):
        drink_type = standardize_drink_name(drink_type)  # 음료 이름 표준화
        logging.warning(f"추가옵션 제거 실행")
        logging.warning(f"현재 옵션: {current_options}, 제거 옵션: {last_remove_option}")

        if drink_type in self.get_orders():
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
    
    def get_temperatures(self):
        # 현재 주문 정보를 반환하는 메서드
        return self.temperatures
    
    def get_sizes(self):
        # 현재 주문 정보를 반환하는 메서드
        return self.sizes

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
                summary_item = f"{summary_item} {number_to_korean(count)} 잔"
                summary.append(summary_item.strip())
        return ", ".join(summary)

order_manager = OrderManager()  # OrderManager 인스턴스 생성

# 엔티티 매핑
class OrderMapper:
    def __init__(self, entities, is_temperature_change=False, is_size_change=False):
        self.entities = sorted(entities, key=lambda x: x['start'])
        self.is_temperature_change = is_temperature_change  # 온도 변경 기능 실행 여부 플래그
        self.is_size_change = is_size_change  # 사이즈 변경 기능 실행 여부 플래그
        self.drinks = []
        self.suffixes = ("사이즈로", "사이즈", "으로", "으", "걸로", "로", "는", "은", "해주세요", "해서", "해", "한거", "이랑", "도")
        if self.check_multi_order():
            self.check_multiple_option()
        else:
            self._map_entities()
        

    # 주문 초기화 메서드
    def _initialize_order(self):
        return {
            "temperature": None,
            "drink_type": None,
            "size": None,
            "quantity": 1,
            "additional_options": [],
        }

    def check_multi_order(self):
        drink_count = self._count_drink_types()
        temperature_count = self._count_temperature_entities()
        quantity_count = self._count_quantity_entities()
        size_count = self._count_size_entities()
        additional_options = self._count_additional_options_entities()
        if drink_count <= temperature_count or drink_count <= quantity_count or drink_count <= size_count or drink_count <= additional_options:
            return True
        else:
            return False
    
    # 엔티티 값에서 제거할 접미사 제거 메서드
    def clean_entity_values(self):
        for entity in self.entities:
            # drink_type 엔티티가 아닌 경우에만 접미사 제거
            if entity['entity'] != 'drink_type':
                value = entity["value"]
                for suffix in self.suffixes:
                    if value.endswith(suffix):
                        value = value[:-len(suffix)]
                        break
                entity["value"] = value

    def check_multiple_option(self):
        current_order = self._initialize_order()
        
        order_Conf = {'order0': {
            'drink_type': [],
            'temperature': [],
            'size': [],
            'quantity': [],
            'additional_options': []
        }}
        
        order = {
            'drink_type': [],
            'temperature': [],
            'size': [],
            'quantity': [],
            'additional_options': []
        }
        
        count = 0
        order_key = f'order{count}'
        drinks = []
        last_drink_type = None  # 마지막으로 언급된 음료 저장

        for entity in self.entities:
            entity_type = entity['entity']
            value = entity['value']
            
            if entity_type == 'drink_type':
                last_drink_type = value  # 음료 타입 저장
                if value in ["아아", "아 아", "아", "아가"]:
                    processed_value = "아메리카노"
                    if not order_Conf[order_key]['drink_type']:
                        order_Conf[order_key]['drink_type'].append(processed_value)
                        order_Conf[order_key]['temperature'].append("아이스")
                    else:
                        count += 1
                        order_key = f'order{count}'
                        order_Conf[order_key] = {
                            'drink_type': [processed_value],
                            'temperature': ["아이스"],
                            'size': [],
                            'quantity': [],
                            'additional_options': []
                        }
                elif value in ["뜨아", "뜨 아", "뜨아아", "또", "응아", "쁘허", "뚜아"]:
                    processed_value = "아메리카노"
                    if not order_Conf[order_key]['drink_type']:
                        order_Conf[order_key]['drink_type'].append(processed_value)
                        order_Conf[order_key]['temperature'].append("핫")
                    else:
                        count += 1
                        order_key = f'order{count}'
                        order_Conf[order_key] = {
                            'drink_type': [processed_value],
                            'temperature': ["핫"],
                            'size': [],
                            'quantity': [],
                            'additional_options': []
                        }    
                elif value in ["아샷추"]:
                    processed_value = "복숭아아이스티"
                    if not order_Conf[order_key]['drink_type']:
                        order_Conf[order_key]['drink_type'].append(processed_value)
                        order_Conf[order_key]['temperature'].append("아이스")
                    else:
                        count += 1
                        order_key = f'order{count}'
                        order_Conf[order_key] = {
                            'drink_type': [processed_value],
                            'temperature': ["아이스"],
                            'size': [],
                            'quantity': [],
                            'additional_options': ["샷"]
                        }
                else:
                    if not order_Conf[order_key]['drink_type']:
                        order_Conf[order_key]['drink_type'].append(value)
                    else:
                        count += 1
                        order_key = f'order{count}'
                        order_Conf[order_key] = {
                            'drink_type': [value],
                            'temperature': [],
                            'size': [],
                            'quantity': [],
                            'additional_options': []
                        }
            elif entity_type == 'temperature':
                # 온도 엔티티가 있지만 현재 주문에 음료가 없는 경우
                if not order_Conf[order_key]['drink_type'] and last_drink_type:
                    # 이전 음료를 사용하여 새 주문 생성
                    order_Conf[order_key]['drink_type'].append(last_drink_type)
                
                if len(order_Conf[order_key][entity_type]) < 2:
                    order_Conf[order_key][entity_type].append(value)
                else:
                    count += 1
                    order_key = f'order{count}'
                    order_Conf[order_key] = {
                        'drink_type': [last_drink_type] if last_drink_type else [],  # 이전 음료 사용
                        'temperature': [value],
                        'size': [],
                        'quantity': [],
                        'additional_options': []
                    }
            elif entity_type in ['size', 'quantity', 'additional_options']:
                if len(order_Conf[order_key][entity_type]) < 2:
                    order_Conf[order_key][entity_type].append(value)
                else:
                    count += 1
                    order_key = f'order{count}'
                    order_Conf[order_key] = {
                        'drink_type': [],
                        'temperature': [],
                        'size': [value] if entity_type == 'size' else [],
                        'quantity': [value] if entity_type == 'quantity' else [],
                        'additional_options': [value] if entity_type == 'additional_options' else []
                    }

        logging.warning(f"처리된 order_Conf: {order_Conf}")

        # order_Conf의 데이터를 order로 통합하고 표준화
        for order_key, order_data in order_Conf.items():
            # 해당 주문에 drink_type이 있는 경우만 처리
            if order_data['drink_type']:
                drink_type = order_data['drink_type'][0]
                temp_count = len(order_data['temperature'])
                
                # temperature가 2개인 경우 drink_type 복제
                if temp_count == 2:
                    order_data['drink_type'] = [drink_type, drink_type]
                
                # 각 필드 처리
                for i in range(max(1, temp_count)):
                    drink_entry = {
                        'drink_type': standardize_drink_name(drink_type),
                        'temperature': standardize_temperature(order_data['temperature'][i]) if i < len(order_data['temperature']) else "핫",
                        'size': standardize_size(order_data['size'][0]) if order_data['size'] else "미디움",
                        'quantity': standardize_quantity(order_data['quantity'][0]) if order_data['quantity'] else "1",
                        'additional_options': [standardize_option(opt) for opt in order_data['additional_options']] if order_data['additional_options'] else []
                    }
                    drinks.append(drink_entry)

        logging.warning(f'최종 처리된 drinks: {drinks}')
        self._complete_order(drinks)
    # 음료와 온도, 잔 수, 사이즈, 추가옵션 매핑 메서드
    def _map_entities(self):
        self.clean_entity_values()
        current_order = self._initialize_order()
        drink_type_count_temp = self._count_drink_types()
        drink_type_count_size = self._count_drink_types()
        temperature_entities_count = self._count_temperature_entities()
        apply_default_temperature = self.is_temperature_change and temperature_entities_count == 1
        size_entities_count = self._count_size_entities()
        apply_default_size = self.is_size_change and size_entities_count == 1

        # 중복 방지를 위한 처리된 엔티티의 범위를 추적
        processed_ranges = set()

        for i, entity in enumerate(self.entities):
            # 이미 처리된 범위에 있는 엔티티는 건너뛰기
            if (entity['start'], entity['end']) in processed_ranges:
                continue

            if entity['entity'] == 'drink_type':
                # 현재 엔티티와 겹치는 다른 drink_type 엔티티가 있는지 확인
                overlapping = False
                for other_entity in self.entities:
                    if (other_entity['entity'] == 'drink_type' and 
                        other_entity is not entity and 
                        ((other_entity['start'] <= entity['start'] <= other_entity['end']) or
                        (entity['start'] <= other_entity['start'] <= entity['end']))):
                        # 겹치는 엔티티가 발견되면, 더 긴 엔티티를 선택
                        overlapping = True
                        if (other_entity['end'] - other_entity['start']) > (entity['end'] - entity['start']):
                            processed_ranges.add((entity['start'], entity['end']))
                            processed_ranges.add((other_entity['start'], other_entity['end']))
                            entity = other_entity
                        else:
                            processed_ranges.add((entity['start'], entity['end']))
                            processed_ranges.add((other_entity['start'], other_entity['end']))
                        break

                if not overlapping:
                    processed_ranges.add((entity['start'], entity['end']))

                if current_order['drink_type']:
                    self._complete_order(current_order)
                    current_order = self._initialize_order()

                drink_value = entity['value']
                
                if drink_value in ["아아", "아 아", "아", "아가"]:
                    current_order['temperature'] = "아이스"
                    current_order['drink_type'] = "아메리카노"
                elif drink_value in ["아샷추", "아삿추"]:
                    current_order['temperature'] = "아이스"
                    current_order['drink_type'] = "복숭아아이스티"
                    current_order['additional_option'] = "샷"
                elif drink_value in ["뜨아", "뜨 아", "뜨아아", "또", "응아", "쁘허", "뚜아"]:
                    current_order['temperature'] = "핫"
                    current_order['drink_type'] = "아메리카노"
                elif entity['value'] in ["마키아또","마끼야도","마키야또","마끼아도","마키아도","마키야도","마까아또","마끼아또"]:
                    current_order['drink_type'] = "카라멜마끼아또"
                else:
                    current_order['drink_type'] = standardize_drink_name(drink_value)
                    
                    if apply_default_temperature:
                        current_order['temperature'] = "핫"
                    else:
                        temp_entity = self._find_previous_or_next_temperature_entity(i)
                        if temp_entity:
                            current_order['temperature'] = temp_entity
                        else:
                            current_order['temperature'] = "핫"

                if apply_default_size:
                    current_order['size'] = "미디움"
                else:
                    size_entity = self._find_next_or_previous_size_entity(i)
                    if size_entity:
                        current_order['size'] = size_entity
                    else:
                        current_order['size'] = "미디움"

            elif entity['entity'] == 'quantity':
                quantity = standardize_quantity(entity['value'])
                current_order['quantity'] = int(quantity) if quantity.isdigit() else korean_to_number(quantity)

            elif entity['entity'] == 'size':
                current_order['size'] = standardize_size(entity['value'])

            elif entity['entity'] == 'additional_options':
                if entity['value'] != '아샷추':
                    current_order['additional_options'].append(standardize_drink_name(standardize_option(entity['value'])))

        if current_order['drink_type']:
            self._complete_order(current_order)

    # 음료 타입 엔티티 개수 반환 메서드
    def _count_drink_types(self):
        return sum(1 for entity in self.entities if entity['entity'] == 'drink_type')

    # 사이즈 엔티티 개수 반환 메서드
    def _count_size_entities(self):
        return sum(1 for entity in self.entities if entity['entity'] == 'size')
    
    # 온도 엔티티 개수 반환 메서드
    def _count_temperature_entities(self):
        return sum(1 for entity in self.entities if entity['entity'] == 'temperature')
    
    def _count_quantity_entities(self):
        return sum(1 for entity in self.entities if entity['entity'] == 'quantity')
    
    def _count_additional_options_entities(self):
        return sum(1 for entity in self.entities if entity['entity'] == 'additional_options')

    # 사이즈 매핑 알고리즘 메서드
    def _find_next_or_previous_size_entity(self, current_index):
        # 음료 종류(drink_type) 바로 뒤의 엔티티가 size인 경우
        if current_index + 1 < len(self.entities) and self.entities[current_index + 1]['entity'] == 'size':
            return standardize_size(self.entities[current_index + 1]['value'])
        
        # 온도 엔티티(temperature) 바로 앞의 엔티티가 size인 경우
        if current_index > 0 and self.entities[current_index - 1]['entity'] == 'temperature':
            if current_index - 2 >= 0 and self.entities[current_index - 2]['entity'] == 'size':
                return standardize_size(self.entities[current_index - 2]['value'])
            
        # 온도 엔티티(temperature)가 없는 경우 음료 종류(drink_type) 바로 앞의 엔티티가 size인 경우
        if current_index > 0 and self.entities[current_index - 1]['entity'] == 'size':
            return standardize_size(self.entities[current_index - 1]['value'])

        # 잔 수(quantity) 엔티티 바로 뒤의 엔티티가 size인 경우
        for i in range(current_index + 1, len(self.entities)):
            if self.entities[i]['entity'] == 'size':
                return standardize_size(self.entities[i]['value'])
            if self.entities[i]['entity'] == 'drink_type':
                break
        return None
     #(매핑 수정 9번 문제점)
    def _find_next_drink_entity(self, current_index):
        for i in range(current_index + 1, len(self.entities)):
            if self.entities[i]['entity'] == 'drink_type':
                return True
            else:
                return False
            
    def _find_next_temperature_entity(self, current_index):
        for i in range(current_index + 1, len(self.entities)):
            if self.entities[i + 1]['entity'] != 'temperature':
                return True
            else:
                return False
   
    # 온도 매핑 알고리즘 메서드
    def _find_previous_or_next_temperature_entity(self, current_index):
        # drink_type의 바로 앞의 엔티티가 temperature인 경우
        if current_index > 0 and self.entities[current_index - 1]['entity'] == 'temperature':
            return self._map_temperature(self.entities[current_index - 1]['value'])
        
        # 뒤의 엔티티 중에서 temperature를 찾음
        for i in range(current_index + 1, len(self.entities)):
            if self.entities[i]['entity'] == 'temperature':
                if i + 1 < len(self.entities) and self.entities[i + 1]['entity'] == 'drink_type':
                    return None
                return self._map_temperature(self.entities[i]['value'])
        return None

    # 온도 값 표준화(아이스, 핫) 후 매핑 메서드
    def _map_temperature(self, value):
        return standardize_temperature(value)

    def _complete_order(self, orders):
        hot_drinks = ["허브티"]
        ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

        # orders가 딕셔너리인 경우 리스트로 변환
        if isinstance(orders, dict):
            orders = [orders]

        for order in orders:
            # 딕셔너리 접근으로 변경
            drink_type = order.get('drink_type', '')
            temperature = order.get('temperature', '')
            size = order.get('size', '')
            quantity = order.get('quantity', 1)
            additional_options = order.get('additional_options', [])

            if drink_type in hot_drinks:
                temperature = "핫"
            elif drink_type in ice_only_drinks:
                temperature = "아이스"
            else:
                if not temperature:
                    temperature = "핫"
            
            if not size:
                size = "미디움"
                
            if not quantity or quantity == []:
                quantity = 1

            # 문자열을 숫자로 변환 (필요한 경우)
            if isinstance(quantity, str):
                try:
                    quantity = int(quantity)
                except ValueError:
                    quantity = korean_to_number(quantity)

            # additional_options 처리
            if isinstance(additional_options, str):
                additional_options = [additional_options]
            elif not additional_options:
                additional_options = []

            # drinks 리스트에 추가할 때는 모든 필드가 포함된 딕셔너리 형태로
            processed_order = {
                'drink_type': drink_type,
                'temperature': temperature,
                'size': size,
                'quantity': quantity,
                'additional_options': additional_options
            }
            
            self.drinks.append(processed_order)


    # 완성된 음료 주문 데이터 반환 메서드
    def get_mapped_data(self):
        logging.warning(self.drinks)
        """
        -완성된 음
        """
        temperatures = [drink["temperature"] for drink in self.drinks]
        drink_types = [drink["drink_type"] for drink in self.drinks]
        sizes = [drink["size"] for drink in self.drinks]
        quantities = [drink["quantity"] for drink in self.drinks]
        additional_options = [", ".join(drink["additional_options"]) for drink in self.drinks]
        return temperatures, drink_types, sizes, quantities, additional_options



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
    makkiato_variations = [
        "마키아또", "마끼야도", "마키야또", "마끼아도", "마키아도", "마키야도", 
        "마까아또", "마끼아또", "마끼", "마키", "카라멜마끼아또", "카라멜마키아또", 
        "카라멜마끼야또", "카라멜마키야또", "카라멜마끼아도", "카라멜마키아도", 
        "카라멜마까아또", "마키아또","마끼야도","마키야또","마끼아도","마키아도",
        "마키야도","마까아또","마끼아또"
    ]

    drink_name_map = {
        # 아메리카노 변형
        "아모리카노": "아메리카노",
        "아메이카노": "아메리카노",
        "아메리까도": "아메리카노",
        "아메리카도": "아메리카노",
        "아메이까노": "아메리카노",
        "아메리카든": "아메리카노",
        "아메리카로": "아메리카노",
        "아메리카나": "아메리카노",
        "아메리카누": "아메리카노",
        "아모니카노": "아메리카노",
        "아아": "아메리카노",
        "아 아": "아메리카노",
        "아": "아메리카노",
        "뜨아": "아메리카노",
        "뜨 아": "아메리카노",
        "뜨아아": "아메리카노",
        "또": "아메리카노",
        "아가": "아메리카노",

        # 카페라떼 변형
        "카페랃떼": "카페라떼",
        "카페라테": "카페라떼",
        "카페라뗴": "카페라떼",
        "카폐라떼": "카페라떼",
        "카페랃떼": "카페라떼",
        "카페라터": "카페라떼",
        "카페라태": "카페라떼",
        "카페라디": "카페라떼",
        "카페나떼": "카페라떼",
        "카페다떼": "카페라떼",
        "카페라트": "카페라떼",
        "카페랏테": "카페라떼",
        "카페랒떼": "카페라떼",
        "라떼": "카페라떼",
        "라뗴": "카페라떼",
        "라때": "카페라떼",

        # 에스프레소 변형
        "에스프래쏘": "에스프레소",
        "에스프레쏘": "에스프레소",
        "에스프라소": "에스프레소",
        "에스프래소": "에스프레소",
        "에스플레소": "에스프레소",
        "에스프러소": "에스프레소",
        "에스프레수": "에스프레소",
        "에스프래수": "에스프레소",
        "에스프래쇼": "에스프레소",
        "에수프레소": "에스프레소",
        "에스페로": "에스프레소",

        # 카푸치노 변형
        "카프치노": "카푸치노",
        "카포치노": "카푸치노",
        "카푸치도": "카푸치노",
        "카푸치로": "카푸치노",
        "카프치로": "카푸치노",
        "카부치노": "카푸치노",
        "카푸취노": "카푸치노",
        "카푸티노": "카푸치노",
        "카푸친누": "카푸치노",
        "카프티노": "카푸치노",

        # 마끼아또 변형
        "카라멜마기아또": "카라멜마끼아또",  # 띄어쓰기 없는 버전 추가
        "마키 아또": "카라멜마끼아또",      # 띄어쓰기 있는 버전 추가
        "카라멜마기아또": "카라멜마끼아또",
        "카라멜마끼야또": "카라멜마끼아또",
        "카라멜마키아또": "카라멜마끼아또",
        "카라멜막혔더": "카라멜마끼아또",
        "마키아또": "카라멜마끼아또",
        "마끼야도": "카라멜마끼아또",
        "마키야또": "카라멜마끼아또",
        "마끼아도": "카라멜마끼아또",
        "마키아도": "카라멜마끼아또",
        "마키야도": "카라멜마끼아또",
        "마까아또": "카라멜마끼아또",
        "마끼아또": "카라멜마끼아또",
        "라벨마끼아또": "카라멜마끼아또",
        "카메라맡기어도": "카라멜마끼아또",
        
        # 말차라떼 변형
        "말자 라떼": "말차라떼",     # 띄어쓰기 버전 추가
        "말자라떼": "말차라떼",
        "말차라태": "말차라떼",
        "말자라테": "말차라떼",
        "말자라태": "말차라떼",
        "말짜라떼": "말차라떼",
        "말짜라태": "말차라떼",
        "말짜라테": "말차라떼",
        "말타라떼": "말차라떼",
        "말타라태": "말차라떼",
        "말사라떼": "말차라떼",
        "말잘할때": "말차라떼",
        "마찰할때": "말차라떼",
        "말찾았대": "말차라떼",
        "말잘했다": "말차라떼",

        # 허브티 변형
        "허부티": "허브티",
        "허브치": "허브티",
        "허브디": "허브티",
        "허브테": "허브티",
        "허브트": "허브티",
        "허브틔": "허브티",
        "허부트": "허브티",
        "허브태": "허브티",
        "허부테": "허브티",
        "허브탸": "허브티",
        "허벅지": "허브티",
        "허버트": "허브티",
        "호텔": "허브티",

        # 밀크티 변형
        "밀크치": "밀크티",
        "밀크테": "밀크티",
        "밀크디": "밀크티",
        "밀크태": "밀크티",
        "밀크틔": "밀크티",
        "밀크트": "밀크티",
        "밀크탸": "밀크티",
        "밀크떼": "밀크티",
        "밀크때": "밀크티",

        # 딸기스무디 변형
        "딸기 스므디": "딸기스무디",   # 띄어쓰기 버전 추가
        "달기스무디": "딸기스무디",
        "따기스무디": "딸기스무디",
        "딸기스므디": "딸기스무디",
        "딸기수무디": "딸기스무디",
        "딸기스무지": "딸기스무디",
        "딸기스므지": "딸기스무디",
        "달기수무디": "딸기스무디",
        "따기수무지": "딸기스무디",
        "딸기스무데": "딸기스무디",
        "달기스무데": "딸기스무디",
        "다기스무디": "딸기스무디",

        # 망고스무디 변형
        "망그스무디": "망고스무디",
        "맹고스무디": "망고스무디",
        "망고스므디": "망고스무디",
        "망고수무디": "망고스무디",
        "망고스무지": "망고스무디",
        "맹고스므디": "망고스무디",
        "망그수무디": "망고스무디",
        "맹고스무지": "망고스무디",
        "망고스무데": "망고스무디",
        "맹고스무데": "망고스무디",
        "망고스머리": "망고스무디",
        "망고스뮤비": "망고스무디",

        # 쿠키앤크림 변형
        "쿠키 엔 크림": "쿠키앤크림",  # 띄어쓰기 버전 추가
        "쿠키엔크림": "쿠키앤크림",
        "쿠키앤크링": "쿠키앤크림",
        "쿠키엔크링": "쿠키앤크림",
        "쿠키앤그림": "쿠키앤크림",
        "쿠키엔그림": "쿠키앤크림",
        "쿠킹앤크림": "쿠키앤크림",
        "쿠킹엔크림": "쿠키앤크림",
        "쿠키안크림": "쿠키앤크림",
        "쿠키앤크린": "쿠키앤크림",
        "쿠키엔크린": "쿠키앤크림",
        "쿠킹크림": "쿠키앤크림",
        "쿠킹그림": "쿠키앤크림",
        "쿠앤크": "쿠키앤크림",

        # 레몬에이드 변형
        "레문에이드": "레몬에이드",
        "래몬에이드": "레몬에이드", 
        "레몬애이드": "레몬에이드",
        "레몬에이들": "레몬에이드",
        "레문애이드": "레몬에이드",
        "래몬애이드": "레몬에이드",
        "레몬에이즈": "레몬에이드",
        "래문에이드": "레몬에이드",
        "레몬에이트": "레몬에이드",
        "레문에이듭": "레몬에이드",
        "레모네이드": "레몬에이드",
        "네모에이드": "레몬에이드",

        # 키위주스 변형
        "키윗주스": "키위주스",
        "키위쥬스": "키위주스",
        "큐위주스": "키위주스",
        "키위즈스": "키위주스",
        "키위쥬쓰": "키위주스",
        "키윗쥬스": "키위주스",
        "큐위쥬스": "키위주스",
        "키위주쓰": "키위주스",
        "키위쭈스": "키위주스",
        "키위쮜스": "키위주스",
        "키즈스": "키위주스",
        "tv스투스": "키위주스",
        "Tv스투스": "키위주스",
        "TV스투스": "키위주스",
        "tv쥬스": "키위주스",
        "Tv쥬스": "키위주스",
        "TV쥬스": "키위주스",

        # 토마토주스 변형
        "토마도주스": "토마토주스",
        "토마토쥬스": "토마토주스",
        "토마토즈스": "토마토주스",
        "토마토쥬쓰": "토마토주스",
        "토마도쥬스": "토마토주스",
        "토마토주쓰": "토마토주스",
        "토마도쮜스": "토마토주스",
        "토마토쮜스": "토마토주스",
        "토마토쭈스": "토마토주스",
        "토마도주쓰": "토마토주스",
        "토마토소스": "토마토주스",

        # 띄어쓰기 있는 버전 추가
        "토마토 쥬스": "토마토주스",
        "토마토 즈스": "토마토주스",
        "토마토 쥬쓰": "토마토주스",
        "토마도 쥬스": "토마토주스",
        "토마토 주쓰": "토마토주스",
        "토마도 쮜스": "토마토주스",
        "토마토 쮜스": "토마토주스",
        "토마토 쭈스": "토마토주스",
        "토마토 소스": "토마토주스",

        # 기타 음료 변형
        "아포가토": "아포카토",
        "아보카도": "아포카토",
        "아프리카": "아포카토",
        "복숭아 ost": "복숭아아이스티",
        "복숭아 st": "복숭아아이스티",
        "복숭아 에스티": "복숭아아이스티",
        "복숭아 하이스틸": "복숭아아이스티",
        "복숭아ost": "복숭아아이스티",
        "복숭아st": "복숭아아이스티",
        "복숭아St": "복숭아아이스티",
        "복숭아ST": "복숭아아이스티",
        "복숭아에스티": "복숭아아이스티",
        "복숭아하이스틸": "복숭아아이스티",
        "복숭아아이스크림": "복숭아아이스티",
        "초콜릿": "초콜릿라떼",
        "초콜릿대": "초콜릿라떼",
        "바닐라떼": "바닐라라떼",
        "바닐라레떼": "바닐라라떼",
        "카페북한": "카페모카",
        "TV 스투스": "키위주스",
        "TV 쥬스": "키위주스",
        "tv 스투스": "키위주스",
        "tv 쥬스": "키위주스",
        
        # 바닐라라떼 관련 추가
        "바닐라 떼": "바닐라라떼",
        "바닐라 레떼": "바닐라라떼",
        
        # 새롭게 추가될 변형들
        "아메": "아메리카노",    # 두 글자 메뉴
        "뜨라": "카페라떼",     # 뜨거운 라떼
        "아라": "카페라떼",     # 아이스 라떼
        "에스": "에스프레소",    # 두 글자 메뉴
        "카푸": "카푸치노",     # 두 글자 메뉴
        "모카": "카페모카",     # 두 글자 메뉴
        "카라": "카라멜마끼아또",  # 두 글자 메뉴
        "바라": "바닐라라떼",    # 두 글자 메뉴
        "아샷": "아메리카노",    # 아메리카노 샷 추가
        "아샷추": "아메리카노",   # 아메리카노 샷 추가
        "아삿추": "아메리카노",   # 아메리카노 샷 추가
        "초라": "초콜릿라떼",    # 두 글자 메뉴
        "뚜아": "아메리카노",    # 뜨아 변형
        "응아": "아메리카노",    # 아메리카노 변형
        "쁘허": "허브티"        # 허브티 변형
    }
    
    return drink_name_map.get(name, name) 

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
    hot_terms = [
        "핫", "따뜻한", "따듯한", "뜨거운", "뜨뜻한", "뜨겁게", "따뜻하게", "따듯하게",
        "따듯함", "뜨거움", "핫트", "따땃함", "따슨", "따순느", "뜨겁그", "따슷한",
        "따순한", "뜨뜻함", "따뜻힌", "핫또", "따신", "따뜻히", "뜨거히", "하수", "hot"
    ]
    
    ice_terms = [
        "아이스", "차가운", "시원한", "시원하게", "차갑게", "차가움", "시원함", "차갑음",
        "아이씨", "아이스르", "시원하그", "아이스트", "차갑은", "시원은", "아이써",
        "시원히", "차갑히", "아이수", "차가이", "시원혀", "아이스으"
    ]
    
    if value in ice_terms:
        return "아이스"
    elif value in hot_terms:
        return "핫"
    return value

# 잔 수를 표준화하는 메서드
def standardize_quantity(value):
    if value in ["한", "앉", "안", "환", "완", "라", "하나", "하낫", "한자", "한단", "하나째", "하나슷"]:
        return "한"
    elif value in ["두", "도", "투", "둘슷", "둘째", "두자", "투자"]:
        return "두"
    elif value in ["세", "재", "대", "서흣", "셋째", "세자", "세상", "세계", "재산"]:
        return "세"
    elif value in ["네", "내", "너얼", "넷째", "내전", "내산", "내장"]:
        return "네"
    elif value in ["다섯", "das", "다서", "다섯슷", "다섯째"]:
        return "다섯"
    elif value in ["여섯", "여섯슷", "여섯째"]:
        return "여섯"
    elif value in ["일곱", "일굽", "일곱슷", "일곱째"]:
        return "일곱"
    elif value in ["여덟", "여덜", "여덟슷", "여덟째"]:
        return "여덟"
    elif value in ["아홉", "아홉슷", "아홉째"]:
        return "아홉"
    elif value in ["열", "열슷", "열째"]:
        return "열"
    elif value in ["1"]:
        return "한"
    elif value in ["2"]:
        return "두"
    elif value in ["3"]:
        return "세"
    elif value in ["4"]:
        return "네"
    elif value in ["5"]:
        return "다섯"
    elif value in ["6"]:
        return "여섯"
    elif value in ["7"]:
        return "일곱"
    elif value in ["8"]:
        return "여덟"
    elif value in ["9"]:
        return "아홉"
    elif value in ["10"]:
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
    if value in ["샤츠", "셔츠", "사추", "샤타나", "4추가", "삿", "샷트", "삿추", 
                 "솟트", "샤트추가", "샤추가", "싯", "솟추", "삿으", "샷으", 
                 "사아트", "소옷", "삿트"]:
        return "샷"
    elif value in ["카라멜실업", "실룩실룩", "가라멜시럽", "카라멜시로", 
                  "카라멜씨럽", "카라메르시럽", "카라멜시롭", "시롭추가", 
                  "카라멜시리얼", "카나멜시럽", "카나멜시로", "씨럽추가"]:
        return "카라멜시럽"
    elif value in ["바닐라실업", "바닐라씨럽", "바니나시럽", "바닐라시로프", 
                   "바닐라시롭", "바닐라시리얼"]:
        return "바닐라시럽"
    elif value in ["비비크림", "휘프크림", "휘핑크링", "휘핑프림", "휘프링", 
                   "휘핑크린", "휘팽크림", "휘핑그림", "휘프킹", "휘팽", 
                   "휘삐", "휘삥", "휘삔"]:
        return "휘핑크림"
    elif value in ["어름", "얼룸", "얼이", "얼음으", "어이스", "어룸", "얼잉",
                   "어름이", "얼으", "얼이음", "어이슬", "어이스으"]:
        return "얼음"
    return value

# 테이크아웃을 표준화하는 메서드
def standardize_take(value):
    if value in ["테이크아웃", "들고", "가져", "먹을", "마실", "아니요"]:
        return "포장"
    elif value in ["먹고", "여기", "이곳", "네","마시"]:
        return "매장"
    return value


# 커피의 종류가 정해지지 않으면 오류 발생 메서드
def raise_missing_attribute_error(drinks):
    if not drinks:
        raise ValueError("정확한 음료의 종류를 말씀하여주세요.")

# 주문
class ActionOrderConfirmation(Action):
    def name(self) -> Text:
        return "action_order_confirmation"

    #학습 된데이터를 받는곳으로 추정.
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # # 현재 주문 정보 초기화(주문을 하는데 이전 주문 정보가 남아있으면 안됨)
            # order_manager.clear_order()
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            user_text = tracker.latest_message.get("text", "")
            
            if "사이즈 업" in user_text:
                raise KeyError("size up")
            # 엔티티를 위치 순서로 정렬
            mapper = OrderMapper(entities)
            
            # 주문 결과를 저장할 딕셔너리
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            
            #(수정 변수)
            logging.warning(f"주문 엔티티: {entities}")
            logging.warning(f"온도, 커피, 사이즈, 잔 수, 옵션: {temperatures} {drink_types} {sizes} {quantities} {additional_options}")
            
            # 고정된 온도 음료의 온도 확인
            hot_drinks = ["허브티"]
            ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]
            for i in range(len(drink_types)):
                if drink_types[i] in hot_drinks and temperatures[i] != "핫":
                    raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
                if drink_types[i] in ice_only_drinks and temperatures[i] != "아이스":
                    raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
            # for i in range(len(drink_types)):
            #     if drink_types[i] in DrinkConstants.HOT_DRINKS and temperatures[i] != "핫":
            #         raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
            #     if drink_types[i] in DrinkConstants.ICE_ONLY_DRINKS and temperatures[i] != "아이스":
            #         raise ValueError(f"{drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
            
            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증
            
            if drink_types and quantities:
                     for i in range(len(drink_types)):
                        order_manager.add_order(drink_types[i], quantities[i], temperatures[i], sizes[i], additional_options[i])
                       
            # 메세지 생성
            confirmation_message = f"주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            # 출력
            dispatcher.utter_message(text=confirmation_message)

        except ValueError as e:
            dispatcher.utter_message(text=str(e))
        except Exception as e:
                dispatcher.utter_message(text=f"주문 접수 중 오류가 발생했습니다: {str(e)}")
        return []
    

# 주문 변경
class ActionModifyOrder(Action):
    def name(self) -> Text:
        return "action_modify_order"

    # 주어진 텍스트 범위 내에서 엔티티 추출
    def extract_entities(self, text, tracker):
        entities = []
        for entity in tracker.latest_message.get("entities", []):
            if entity.get("extractor") != "DIETClassifier" and entity["start"] >= text["start"] and entity["end"] <= text["end"]:
                entities.append(entity)
        return entities

    # 액션 실행 메소드
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 가장 최근 사용자 메시지에서 엔티티 추출
            modify_entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
        
            mapper = OrderMapper(modify_entities)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()
            user_text = tracker.latest_message.get("text", "")

            logging.warning(f"사용자 주문 변경 입력 내용: {modify_entities}")
            logging.warning(f"사용자 주문 변경 입력 내용: {user_text}")

            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # '대신' 또는 '말고'를 사용하여 주문 변경 여부 확인
            if "대신" in user_text or "말고" in user_text or "은" in user_text or "는" in user_text:
                # '대신' 또는 '말고'를 기준으로 텍스트 분리
                split_text = re.split("대신|말고|은|는", user_text)
                logging.warning(f"매칭 시도: {split_text}")
                if len(split_text) == 2:
                    target_part = {"text": split_text[0].strip(), "start": 0, "end": len(split_text[0].strip())}
                    new_part = {"text": split_text[1].strip(), "start": len(split_text[0]) + 2, "end": len(user_text)}

                    logging.warning(f"target_part 내용: {target_part}")
                    logging.warning(f"new_part 내용: {new_part}")

                    # 각각의 텍스트 부분에서 엔티티 추출
                    target_entities = self.extract_entities(target_part, tracker)
                    new_entities = self.extract_entities(new_part, tracker)

                    logging.warning(f"target_entities 내용: {target_entities}")
                    logging.warning(f"new_entities 내용: {new_entities}")

                    # 대상 및 새 엔티티를 매핑하여 데이터 추출
                    target_mapper = OrderMapper(target_entities)
                    target_temperatures, target_drink_types, target_sizes, target_quantities, target_additional_options = target_mapper.get_mapped_data()

                    new_mapper = OrderMapper(new_entities)
                    new_temperatures, new_drink_types, new_sizes, new_quantities, new_additional_options = new_mapper.get_mapped_data()

                    logging.warning(f"target_mapper 내용: {target_temperatures, target_drink_types, target_sizes, target_quantities, target_additional_options}")
                    logging.warning(f"new_mapper 내용: {new_temperatures, new_drink_types, new_sizes, new_quantities, new_additional_options}")

                    # 고정된 온도 음료의 온도 확인
                    hot_drinks = ["허브티"]
                    ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

                    for i in range(len(new_drink_types)):
                        if new_drink_types[i] in hot_drinks and new_temperatures[i] != "핫":
                            raise ValueError(f"{new_drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")
                        if new_drink_types[i] in ice_only_drinks and new_temperatures[i] != "아이스":
                            raise ValueError(f"{new_drink_types[i]}는(은) 온도를 변경하실 수 없습니다.")

                    # 기존 주문에서 대상 항목 제거, 제거할 음료, 수량, 온도, 사이즈, 추가 옵션을 가져옵니다.
                    for i in range(len(target_drink_types)):
                        target_drink = target_drink_types[i]
                        target_quantity = target_quantities[i]
                        target_temperature = target_temperatures[i] if i < len(target_temperatures) else None
                        target_size = target_sizes[i] if i < len(target_sizes) else None
                        target_option = target_additional_options[i] if i < len(target_additional_options) else None
                        # 현재 주문 목록을 가져와서 target_drink가 목록에 있는지 확인합니다.
                        # 음료가 ㄻ하면 order_manager.subtract_order를 호출하여 해당 음료를 주문에서 제거합니다.
                        if target_drink in order_manager.get_orders():
                            order_manager.subtract_order(target_drink, target_quantity, target_temperature, target_size, target_option)
                        else:
                            dispatcher.utter_message(text=f"{target_drink}은(는) 주문에 없습니다.")
                            return []

                    # 새 항목을 기존 주문에 추가, 추가할 음료, 수량, 온도, 사이즈, 추가 옵션을 가져옵니다.
                    for i in range(len(new_drink_types)):
                        new_drink = new_drink_types[i]
                        new_quantity = new_quantities[i]
                        new_size = new_sizes[i] if i < len(new_sizes) else None
                        new_temperature = new_temperatures[i] if i < len(new_temperatures) else None
                        new_option = new_additional_options[i] if i < len(new_additional_options) else None

                        if new_drink in order_manager.ice_only_drinks:
                            dispatcher.utter_message(text=f"{new_drink}는 아이스만 가능합니다.")
                            new_temperature = "아이스"
                        elif new_drink in order_manager.hot_drinks:
                            dispatcher.utter_message(text=f"{new_drink}는 핫만 가능합니다.")
                            new_temperature = "핫"
                        # 해당 음료를 주문에 추가합니다.
                        order_manager.add_order(new_drink, new_quantity, new_temperature, new_size, new_option)
            else:
                # '대신' 또는 '말고', '은', '는' 이 없을 경우, 기존 주문을 비우고 새로 추가
                order_manager.clear_order()

                logging.warning(f"주문 변경 엔티티: {modify_entities}")

                for i in range(len(drink_types)):
                    new_drink = drink_types[i]
                    new_quantity = quantities[i]
                    new_size = sizes[i] if i < len(sizes) else None
                    new_temperature = temperatures[i] if i < len(temperatures) else None
                    new_option = additional_options[i] if i < len(additional_options) else None

                    if new_drink in order_manager.ice_only_drinks:
                        dispatcher.utter_message(text=f"{new_drink}는 아이스만 가능합니다.")
                        new_temperature = "아이스"
                    elif new_drink in order_manager.hot_drinks:
                        dispatcher.utter_message(text=f"{new_drink}는 핫만 가능합니다.")
                        new_temperature = "핫"

                    order_manager.add_order(new_drink, new_quantity, new_temperature, new_size, new_option)

            # 최종 주문 확인 메시지 생성 및 출력
            confirmation_message = f"주문이 수정되었습니다. 현재 주문은 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)
            return []
        except Exception as e:
            dispatcher.utter_message(text=f"주문 변경 중 오류가 발생했습니다: {str(e)}")
            return []

#주문 제거
class ActionSubtractFromOrder(Action):

    def name(self) -> Text:
        # 액션의 이름을 반환하는 메소드
        return "action_subtract_from_order"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 DIETClassifier가 아닌 엔티티들을 가져옴
            subtract_entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            logging.warning(subtract_entities)
            # OrderMapper를 사용하여 엔티티들을 매핑
            mapper = OrderMapper(subtract_entities)
            manager = OrderManager()
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            logging.warning(f"사용자 주문 제거 입력 내용: {subtract_entities}")
            logging.warning(f"사용자 주문 제거 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증(아이스 들어간 음료 다 취소. 가 드링크 타입이 없는데 왜 에러가 안뜨지?)
            
            # 매핑된 데이터를 순회하면서 주문 제거
            for i in range(len(drink_types)):
                drink = drink_types[i]  # 음료 종류
                quantity = quantities[i]  # 잔 수 여기에 if quantities[i] == "전부" : quantity = ordermanager.get_orders()
                size = sizes[i] if i < len(sizes) else None  # 사이즈
                temperature = temperatures[i] if i < len(temperatures) else None  # 온도
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션
                
                try:
                    # 주문에 해당 음료가 있는지 확인하고 제거
                    if drink in order_manager.get_orders():
                        logging.warning(f"{temperature, drink, size, quantity, additional_option}")
                        order_manager.subtract_order(drink, quantity, temperature, size, additional_option)
                    else:
                        raise ValueError(f"{drink}은(는) 등록되지 않은 커피입니다! 다시 주문해주세요.")
                except ValueError as e:
                    dispatcher.utter_message(text=str(e))

            # 남아있는 주문이 있는지 확인하고 사용자에게 메시지 전송
            if order_manager.get_orders():
                confirmation_sub_message = ""
                for i in range(len(drink_types)):
                        drink = drink_types[i]  # 음료 종류
                        quantity = quantities[i]  # 잔 수
                        size = sizes[i] if i < len(sizes) else None  # 사이즈
                        temperature = temperatures[i] if i < len(temperatures) else None  # 온도
                        sub_message = f"{temperature} {drink} {size} {number_to_korean(quantity)}잔 "
                        confirmation_sub_message += sub_message 
                confirmation_message = f"{confirmation_sub_message}이 제거되었습니다. 현재 주문은 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
                dispatcher.utter_message(text=confirmation_message)
            else:
                dispatcher.utter_message(text="모든 음료가 주문에서 제거되었습니다.")

            return []
        except ValueError as e:
            dispatcher.utter_message(text=str(e))
        except Exception as e:
            # 오류 발생 시 사용자에게 오류 메시지 전송
            dispatcher.utter_message(text=f"주문 제거 중 오류가 발생했습니다: {str(e)}")
            return []
#주문 제거
# class ActionSubtractFromOrders(Action):

#     def name(self) -> Text:
#         # 액션의 이름을 반환하는 메소드
#         return "action_subtract_from_order"
#     async def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         try:
#             # 현재 의도(intent)와 메시지 텍스트 확인
#             current_intent = tracker.latest_message.get('intent', {}).get('name')
#             user_message = tracker.latest_message.get('text', '').lower()
            
#             # 디버깅을 위한 로그 추가
#             logging.warning(f"Current intent: {current_intent}")
#             logging.warning(f"User message: {user_message}")

#             # 제거 관련 키워드 정의
#             removal_keywords = ['취소', '빼', '제거', '삭제', '지워', '없애', '안 넣어']
            
#             # 명시적인 제거 의도 확인
#             has_removal_keyword = any(keyword in user_message for keyword in removal_keywords)
            
#             # 주문 추가 관련 키워드
#             order_keywords = ['주문', '주세요', '할게요', '드릴게요', '원해요', '씨켜주세요', '식혀주세요']
#             has_order_keyword = any(keyword in user_message for keyword in order_keywords)

#             # 주문 추가로 처리해야 하는 경우
#             if has_order_keyword or not has_removal_keyword:
#                 # 주문 추가 액션으로 리다이렉트
#                 from rasa_sdk.events import FollowupAction
#                 dispatcher.utter_message(text="주문을 추가하겠습니다.")
#                 return [FollowupAction("action_order_confirmation")]

#             # 여기서부터는 실제 제거 로직
#             subtract_entities = [entity for entity in tracker.latest_message.get("entities", []) 
#                             if entity.get("extractor") != "DIETClassifier"]
            
#             logging.warning(f"사용자 주문 제거 입력 내용: {subtract_entities}")
            
#             mapper = OrderMapper(subtract_entities)
#             temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

#             logging.warning(f"사용자 주문 제거 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

#             # 제거 로직 실행
#             for i in range(len(drink_types)):
#                 drink = drink_types[i]
#                 quantity = quantities[i]
#                 size = sizes[i] if i < len(sizes) else None
#                 temperature = temperatures[i] if i < len(temperatures) else None
#                 additional_option = additional_options[i] if i < len(additional_options) else None
                
#                 try:
#                     if drink in order_manager.get_orders():
#                         logging.warning(f"Removing: {temperature, drink, size, quantity, additional_option}")
#                         order_manager.subtract_order(drink, quantity, temperature, size, additional_option)
#                     else:
#                         raise ValueError(f"{drink}은(는) 등록되지 않은 커피입니다! 다시 주문해주세요.")
#                 except ValueError as e:
#                     dispatcher.utter_message(text=str(e))

#             # 결과 메시지 생성
#             if order_manager.get_orders():
#                 confirmation_sub_message = ""
#                 for i in range(len(drink_types)):
#                     drink = drink_types[i]
#                     quantity = quantities[i]
#                     size = sizes[i] if i < len(sizes) else None
#                     temperature = temperatures[i] if i < len(temperatures) else None
#                     sub_message = f"{temperature} {drink} {size} {number_to_korean(quantity)}잔 "
#                     confirmation_sub_message += sub_message 
#                 confirmation_message = f"{confirmation_sub_message}이 제거되었습니다. 현재 주문은 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
#                 dispatcher.utter_message(text=confirmation_message)
#             else:
#                 dispatcher.utter_message(text="모든 음료가 주문에서 제거되었습니다.")

#             return []
            
#         except Exception as e:
#             logging.exception("Error in action_subtract_from_order")
#             dispatcher.utter_message(text=f"주문 제거 중 오류가 발생했습니다: {str(e)}")
#             return []

# 주문 다중처리
class ActionAddSubtract(Action):
    def name(self) -> Text:
        return "action_add_subtract"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 엔티티 가져오기
            entities = sorted([entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"], key=lambda x: x['start'])

            add_entities = []
            subtract_entities = []

            current_order = self._initialize_order()
            # 추가하는 부분과 제거하는 부분을 나누기 위한 값을 저장.
            current_action = None

            logging.warning(f"주문 다중처리 엔티티: {entities}")
            
            # 엔티티를 인덱스 값과 같이 가장 처음부터 순서대로 반복합니다.
            for i, entity in enumerate(entities):
                # 현재 엔티티의 entity가 'add'면서 리스트의 첫 번째 엔티티가 'add'거나 'add'엔티티가 'additional_options' 뒤에 있지 않으면(뒤에 있으면 추가옵션 꺼)
                if entity['entity'] == 'add' and (i == 0 or entities[i-1]['entity'] != 'additional_options'):
                    current_action = 'add' # 추가하는 부분
                    if current_order['drink_type']:
                        add_entities.append(current_order)
                    current_order = self._initialize_order() # 새로운 주문을 시작하기 위해 현재 주문을 초기화
                    logging.warning(f"다중처리 추가 : {add_entities}")
                elif entity['entity'] == 'subtract':
                    current_action = 'subtract' # 제거하는 부분
                    if current_order['drink_type']:
                        subtract_entities.append(current_order)
                    current_order = self._initialize_order() # 새로운 주문을 시작하기 위해 현재 주문을 초기화
                    logging.warning(f"다중처리 제거 : {subtract_entities}")
                else:
                    self._map_entity_to_order(entity, current_order)

            # 누락 주문 처리(다중처리 인텐트가 인식되서 기능은 실행이 되었는데 채팅이 ~는 추가해주시고 나 ~는 빼주시고 에서 말이 끊기거나 했을 때 실행되도록)
            if current_order['drink_type']:
                if current_action == 'add':
                    add_entities.append(current_order)
                elif current_action == 'subtract':
                    subtract_entities.append(current_order)

            # 온도의 기본값을 매핑
            self._set_default_temperature(add_entities)
            self._set_default_temperature(subtract_entities)

            # 매핑된 데이터 출력
            logging.warning(f"추가 엔티티: {add_entities}, 제거 엔티티: {subtract_entities}")

            # 추가 엔티티가 있는 경우 처리
            for order in add_entities:
                self._process_add(order)

            # 제거 엔티티가 있는 경우 처리
            for order in subtract_entities:
                self._process_subtract(order, dispatcher)

            # 정리된 최종 주문 리스트를 생성
            confirmation_message = f"주문이 수정되었습니다. 현재 주문은 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)
            return []
        except Exception as e:
            logging.exception("Exception occurred in action_add_subtract")
            dispatcher.utter_message(text=str(e))
            return []

    # 음료의 종류와 온도를 제외한 기본값 메서드
    def _initialize_order(self):
        return {
            "temperature": None,
            "drink_type": None,
            "size": "미디움",
            "quantity": 1,
            "additional_options": []
        }

    # 음료 매핑 메서드 (궁금)
    def _map_entity_to_order(self, entity, order):
        if entity['entity'] == 'drink_type':
            # 사용자 정의 음료 종류 설정
            if entity['value'] in ["아아", "아 아", "아", "아가"]:
                order['drink_type'] = "아메리카노"
                order['temperature'] = "아이스"
            elif entity['value'] in ["뜨아", "뜨 아", "뜨아아", "또", "응아", "쁘허", "뚜아"]:
                order['drink_type'] = "아메리카노"
                order['temperature'] = "핫"
            else:
                order['drink_type'] = standardize_drink_name(entity['value'])
        elif entity['entity'] == 'quantity':
            quantity = entity['value']
            order['quantity'] = int(quantity) if quantity.isdigit() else korean_to_number(quantity)
        elif entity['entity'] == 'temperature':
            if order['temperature'] is None:
                order['temperature'] = standardize_temperature(entity['value'])
        elif entity['entity'] == 'size':
            order['size'] = standardize_size(entity['value'])
        elif entity['entity'] == 'additional_options':
            order['additional_options'].append(standardize_option(entity['value']))

    # 온도 기본값 성정 메서드
    def _set_default_temperature(self, orders):
        hot_drinks = ["허브티"]
        ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

        for order in orders:
            if order['temperature'] is None:
                if order['drink_type'] in hot_drinks:
                    order['temperature'] = "핫"
                elif order['drink_type'] in ice_only_drinks:
                    order['temperature'] = "아이스"
                else:
                    order['temperature'] = "핫"
            else:
                # 온도가 이미 설정되었고 온도가 고정된 음료의 온도가 잘못되었을 때
                if order['drink_type'] in hot_drinks and order['temperature'] != "핫":
                    raise ValueError(f"{order['drink_type']}는(은) 온도가 핫으로 고정된 음료입니다! 다시 주문해 주세요.")
                elif order['drink_type'] in ice_only_drinks and order['temperature'] != "아이스":
                    raise ValueError(f"{order['drink_type']}는(은) 온도가 아이스로 고정된 음료입니다! 다시 주문해 주세요.")

    # 음료 제거 메서드
    def _process_subtract(self, order, dispatcher):
        try:
            if order['drink_type'] in order_manager.get_orders():
                order_manager.subtract_order(order['drink_type'], order['quantity'], order['temperature'], order['size'], ", ".join(order['additional_options']))
            else:
                raise ValueError(f"{order['drink_type']}은(는) 등록되지 않은 커피입니다! 다시 주문해주세요.")
        except ValueError as e:
            dispatcher.utter_message(text=str(e))

    # 음료 추가 메서드
    def _process_add(self, order):
        order_manager.add_order(order['drink_type'], order['quantity'], order['temperature'], order['size'], ", ".join(order['additional_options']))
        
# 주문 확인
class ActionOrderFinish(Action):
    def name(self) -> Text:
        return "action_order_finish"

    # 주문을 완료하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 주문 데이터 확인
            if not order_manager.get_orders():
                # 주문이 없는 경우
                dispatcher.utter_message(text="장바구니에 주문이 없습니다. 다시 주문해 주세요.")
                return []
            
            # 최종 주문 메시지 생성
            final_message = f"주문하신 음료는 {order_manager.get_order_summary()}입니다."
            dispatcher.utter_message(text=final_message)
            dispatcher.utter_message(response="utter_takeout")

            # 주문 완료 후 저장된 커피 데이터 초기화
            order_manager.clear_order()

            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_order_finish")
            dispatcher.utter_message(text="결제 중 오류가 발생했습니다. 다시 시도해주세요.")
            return []

# 주문 취소
class ActionCancelOrder(Action):
    def name(self) -> Text:
        return "action_cancel_order"

    # 주문을 취소하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 현재 주문된 음료 목록 가져오기
            current_orders = order_manager.get_orders()

            if not current_orders:
                # 취소할 주문이 없는 경우
                dispatcher.utter_message(text="취소할 주문이 없습니다.")
                return []

            # 주문 취소 메시지 생성
            cancellation_message = f"모든 주문이 취소되었습니다. 취소된 음료는 {order_manager.get_order_summary()}입니다. 새로운 주문을 원하시면 말씀해주세요."
            order_manager.clear_order()
            
            dispatcher.utter_message(text=cancellation_message)
            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_cancel_order")
            dispatcher.utter_message(text="주문을 취소하는 중에 오류가 발생했습니다. 다시 시도해주세요.")
            return []

# 커피 추천
class ActionCoffeeRecommendation(Action):
    def name(self) -> Text:
        return "action_coffee_recommendation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        recommended_coffees = ["아메리카노", "카페라떼", "카푸치노", "에스프레소"]
        recommended_coffees_str = ", ".join(recommended_coffees)
        recommedded_message = f"저희 매장이 추천하는 커피로는 {recommended_coffees_str} 등이 있습니다. 어떤 커피을 원하시나요?"
        # recommedded_message = f"{recommedded_text} {recommended_coffees_str} 등이 있습니다. 어떤 것을 원하시나요?"
        dispatcher.utter_message(text=recommedded_message)

        return []

# 커피 사이즈 변경
class ActionSelectCoffeeSize(Action):
    def name(self) -> Text:
        return "action_select_coffee_size"  # 액션의 이름을 정의하는 메서드

    # start 값이 가장 큰, 즉 사용자의 대화에서 가장 마지막에 오는 size 엔티티 값을 추출
    def extract_last_size(self, entities):
        # size 엔티티를 필터링하여 해당 엔티티들만 리스트로 만듦
        size_entities = [entity for entity in entities if entity["entity"] == "size"]
        # 필터링된 size 엔티티가 있을 경우
        if size_entities:
            # 'start' 값을 기준으로 가장 큰 엔티티를 찾고, 해당 엔티티의 'value' 값을 반환
            return max(size_entities, key=lambda x: x['start'])["value"]
        return None  # size 엔티티가 없을 경우 None 반환

    # 커피 사이즈를 변경하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            user_text = tracker.latest_message.get("text", "")

            if "사이즈 업" in user_text:
                raise KeyError("size up")

            # 엔티티를 위치 순서로 정렬하고 매핑
            mapper = OrderMapper(entities, is_size_change=True)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 로그로 입력된 엔티티와 매핑된 데이터를 출력
            logging.warning(f"커피 사이즈 변경 입력 내용 텍스트: {user_text}")
            logging.warning(f"커피 사이즈 변경 입력 내용 엔티티: {entities}")
            logging.warning(f"커피 사이즈 변경 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 가장 마지막에 오는 size 엔티티 값을 new_size로 설정
            new_size = self.extract_last_size(entities)

            if new_size is None:
                new_size = "미디움"
                #dispatcher.utter_message(text="새로운 사이즈를 지정해주세요.")
                #return []  # 새로운 사이즈가 지정되지 않으면 메서드를 종료

            # 현재 사이즈를 구분
            current_sizes = [entity["value"] for entity in entities if entity["entity"] == "size" and entity["value"] != new_size]
            current_size = current_sizes[-1] if current_sizes else "미디움"

            for i in range(len(drink_types)):
                drink = drink_types[i]  # 변경할 음료의 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 변경할 음료의 수량
                temperature = temperatures[i] if i < len(temperatures) else None  # 음료의 온도
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션

                # 로그로 변경할 음료의 정보 출력
                logging.warning(f"온도: {temperature}, 변경 대상 음료: {drink}, 수량: {quantity}, 현재 사이즈: {current_size}, 새로운 사이즈: {new_size}")

                try:
                    # 현재 주문된 음료를 기존 사이즈로 제거
                    order_manager.subtract_order(drink, quantity, temperature, current_size, additional_option)
                    # 새로운 사이즈로 주문 추가
                    order_manager.add_order(drink, quantity, temperature, new_size, additional_option)
                except ValueError as e:
                    # 오류 발생 시 사용자에게 메시지 전달
                    dispatcher.utter_message(text=str(e))
                    return []

            # 사이즈 변경 완료 메시지 생성 및 사용자에게 전달
            confirmation_message = f"사이즈가 변경되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text=f"사이즈 변경 중 오류가 발생했습니다: {str(e)}")
            return []

# 커피 온도 변경
class ActionSelectCoffeeTemperature(Action):
    def name(self) -> Text:
        return "action_select_coffee_temperature"  # 액션의 이름을 정의하는 메서드

    # 가장 마지막에 오는 temperature 엔티티 값을 추출하고 변환
    def extract_last_temperature(self, entities):
        # temperature 엔티티를 필터링하여 해당 엔티티들만 리스트로 만듦
        temperature_entities = [entity for entity in entities if entity["entity"] == "temperature"]
        if temperature_entities:
            last_temp = max(temperature_entities, key=lambda x: x['start'])["value"]
            # '차갑게', '시원하게', '뜨겁게', '따뜻하게'를 각각 '아이스'와 '핫'으로 변환
            if last_temp in ["차갑게", "시원하게", "차가운", "시원한"]:
                return "아이스"
            elif last_temp in ["뜨겁게", "따뜻하게", "뜨거운", "따뜻한", "뜨뜻한", "따듯한"]:
                return "핫"
            return standardize_temperature(last_temp)
        return None  # temperature 엔티티가 없을 경우 None 반환

    # 커피 온도를 변경하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최근 사용자 메시지에서 엔터티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            # 엔티티를 위치 순서로 정렬하고 매핑
            mapper = OrderMapper(entities, is_temperature_change=True)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 로그로 입력된 엔티티와 매핑된 데이터를 출력
            logging.warning(f"커피 온도 변경 입력 내용: {entities}")
            logging.warning(f"커피 온도 변경 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            # 고정된 온도 음료의 온도 확인
            hot_drinks = ["허브티"]
            ice_only_drinks = ["토마토주스", "키위주스", "망고스무디", "딸기스무디", "레몬에이드", "복숭아아이스티"]

            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 가장 마지막에 오는 temperature 엔티티 값을 new_temperature로 설정
            new_temperature = self.extract_last_temperature(entities)

            if new_temperature is None:
                dispatcher.utter_message(text="새로운 온도를 지정해주세요.")
                return []  # 새로운 온도가 지정되지 않으면 메서드를 종료

            for i in range(len(drink_types)):
                drink = drink_types[i]  # 변경할 음료의 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 변경할 음료의 수량
                size = sizes[i] if i < len(sizes) else "미디움"  # 음료의 사이즈
                additional_option = additional_options[i] if i < len(additional_options) else None  # 추가 옵션

                # 기존 주문에서 현재 온도를 가져옴
                current_temperature = temperatures[i] if i < len(temperatures) else None

                # 음료가 핫 드링크인데 새로운 온도가 아이스라면 에러 발생
                if drink in hot_drinks and new_temperature == "아이스":
                    raise ValueError(f"{drink}는(은) 아이스로 변경할 수 없습니다.")
                # 음료가 아이스 드링크인데 새로운 온도가 핫이라면 에러 발생
                if drink in ice_only_drinks and new_temperature == "핫":
                    raise ValueError(f"{drink}는(은) 핫으로 변경할 수 없습니다.")

                # 로그로 변경할 음료의 정보 출력
                logging.warning(f"변경 대상 음료: {drink}, 수량: {quantity}, 현재 온도: {current_temperature}, 새로운 온도: {new_temperature}, 사이즈: {size}, 추가 옵션: {additional_option}")

                try:
                    # 현재 주문된 음료를 기존 온도로 제거
                    order_manager.subtract_order(drink, quantity, current_temperature, size, additional_option)
                    # 새로운 온도로 주문 추가
                    order_manager.add_order(drink, quantity, new_temperature, size, additional_option)
                except ValueError as e:
                    # 오류 발생 시 사용자에게 메시지 전달
                    dispatcher.utter_message(text=str(e))
                    return []

            # 온도 변경 완료 메시지 생성 및 사용자에게 전달
            confirmation_message = f"온도를 변경하셨습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text=f"커피 온도 변경 중 오류가 발생했습니다: {str(e)}")
            return []

# 커피 추가옵션 추가
# class ActionAddAdditionalOption(Action):
#     def name(self) -> Text:
#         return "action_add_additional_option"
    
#     async def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         try:
#             # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
#             # logging.warning(order_manager.get_orders())
#             entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
#             mapper = OrderMapper(entities)
#             temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()
           
#             add_indices = [i for i, entity in enumerate(entities) if entity['entity'] == 'add']

                                            
#                     # OrderMapper를 사용하여 엔티티를 매핑
#             mapper = OrderMapper(entities)
#             temperatures, drink_types, sizes, quantities, add_additional_options = mapper.get_mapped_data()
                                        
#             if add_indices:
#                      # 'add' 엔티티가 하나만 있는 경우 모든 옵션을 추가

#                         if len(add_indices) == 1:
#                             logging.warning(f"add 엔티티 하나 있음")
                                                                
#                                                                 # 디버깅을 위한 로그 출력
#                             logging.warning(f"추가 옵션 추가 입력 내용: {entities}")
#                             logging.warning(f"추가 옵션 추가 매핑 데이터: {temperatures, drink_types, sizes, quantities, add_additional_options}")     

#                                                                         # 음료 속성 검증
#                             raise_missing_attribute_error(mapper.drinks)  

#                             # 매핑된 데이터를 사용하여 주문 정보 업데이트
#                             for i in range(len(drink_types)):
#                                 drink = drink_types[i]  # 음료 종류
#                                 quantity = quantities[i] if quantities[i] is not None else 1  # 잔 수
#                                 temperature = temperatures[i] if i < len(temperatures) else "핫"  # 온도
#                                 size = sizes[i] if i < len(sizes) else "미디움"  # 사이즈
#                                 add_additional_options = add_additional_options[i] if i < len(add_additional_options) else []  # 추가 옵션

#                                 current_option = []

#                                 # 디버깅을 위한 로그 출력
#                                 logging.warning(f"현재 옵션: {current_option}")
#                                 logging.warning(f"추가 옵션: {add_additional_options}")
                                
#                                 if add_additional_options:
#                                         # add_additional_options 메서드를 호출하여 추가 옵션 추가
#                                     order_manager.add_additional_options(drink, quantity, temperature, size, current_option, add_additional_options)
#                                 else: 
#                                     # 추가라는 것을 받아들였을때 샷이 없을 경우에도 주문으로 처리 되도록
#                                     order_manager.add_order(drink, quantity, temperature, size, add_additional_options)
#                                     # 최종 확인 메시지 생성 및 사용자에게 전달
#                                 confirmation_message = f"말씀하신 옵션이 추가 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
#                                 dispatcher.utter_message(text=confirmation_message)
#                                 return []
#                                 # 'add' 엔티티가 2개 이상인 경우
#                         elif len(add_indices) > 1:
#                             logging.warning(f"add 엔티티 여러개 있음")
#                             # 마지막 'add' 엔티티의 인덱스
#                             last_add_index = add_indices[-1]

#                             # 마지막 'add' 엔티티 이전의 엔티티를 매핑
#                             before_last_add_entities = entities[:last_add_index]
#                             # 마지막 'add' 엔티티 이후의 엔티티 중 'additional_options' 엔티티만 추출
#                             between_add_entities = entities[add_indices[-2] + 1:last_add_index]
                                                                        
#                             logging.warning(f"마지막 add 엔티티 이전 : {before_last_add_entities}")
#                             logging.warning(f"마지막 add 엔티티 사이의 엔티티 : {between_add_entities}")

#                             # 마지막 'add' 엔티티 이전의 엔티티를 매핑
#                             current_mapper = OrderMapper(before_last_add_entities)
#                             current_temperatures, current_drink_types, current_sizes, current_quantities, current_additional_options = current_mapper.get_mapped_data()

#                             # 'additional_options' 엔티티만 추출
#                             add_additional_options = [entity['value'] for entity in between_add_entities if entity['entity'] == 'additional_options']

#                             # 현재 옵션에서 추가 옵션을 제거
#                             # current_additional_options가 문자열이라면 split하여 리스트로 변환
#                             current_additional_options_list = []
#                             for option in current_additional_options:
#                                 current_additional_options_list.extend(option.split(', '))

#                             # 추가 옵션에서 중복 제거된 항목만 남기기
#                                 current_additional_options = [
#                                 option for option in current_additional_options_list
#                                 if option not in add_additional_options
#                                 ]

#                                 # 추가 옵션 표준화
#                                 add_additional_options = [standardize_option(option) for option in add_additional_options]

#                                 # 디버깅을 위한 로그 출력
#                                 logging.warning(f"현재 옵션: {current_additional_options}")
#                                 logging.warning(f"추가 옵션: {add_additional_options}")

#                                 # 현재 옵션과 추가 옵션을 비교하여 업데이트
#                                 for i in range(len(current_drink_types)):
#                                     drink = current_drink_types[i]  # 음료 종류
#                                     quantity = current_quantities[i] if current_quantities[i] is not None else 1  # 잔 수
#                                     temperature = current_temperatures[i] if i < len(current_temperatures) else "핫"  # 온도
#                                     size = current_sizes[i] if i < len(current_sizes) else "미디움"  # 사이즈
#                                     current_option = current_additional_options[i] if i < len(current_additional_options) else []  # 현재 추가 옵션

#                                     logging.warning(f"업뎃: {drink, quantity, temperature, size, current_option}")

#                                     if current_option:
#                                         # 추가 옵션으로 업데이트
#                                         order_manager.add_additional_options(drink, quantity, temperature, size, current_option, add_additional_options)

#                                     # 최종 확인 메시지 생성 및 사용자에게 전달
#                                         confirmation_message = f"말씀하신 옵션이 추가 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
#                                         dispatcher.utter_message(text=confirmation_message)

#                                         return []
#                                     else:
#                                         order_manager.add_order(drink_types, quantities, temperatures, sizes, add_additional_options)

#             return []
#         except Exception as e:
#             # 예외 발생 시 사용자에게 메시지 전달
#             dispatcher.utter_message(text="추가 옵션 추가 중 문제가 발생했습니다. 다시 시도해 주세요.")
#             # 예외 상세 로그 출력
#             logging.exception("Exception occurred in action_add_additional_option")
#             return []
# 커피 추가옵션 추가
class ActionAddAdditionalOption(Action):
    def name(self) -> Text:
        return "action_add_additional_option"
    
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            mapper = OrderMapper(entities)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()
           
            # 디버깅을 위한 로그 출력
            logging.warning(f"추가 옵션 추가 입력 내용: {entities}")
            logging.warning(f"추가 옵션 추가 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")     

            # 음료 속성 검증
            raise_missing_attribute_error(mapper.drinks)  

            # 매핑된 데이터를 사용하여 주문 정보 업데이트
            for i in range(len(drink_types)):
                drink = drink_types[i]
                quantity = quantities[i] if quantities[i] is not None else 1
                temperature = temperatures[i] if i < len(temperatures) else "핫"
                size = sizes[i] if i < len(sizes) else "미디움"
                add_additional_options = additional_options[i] if i < len(additional_options) else []

                current_option = []

                # 디버깅을 위한 로그 출력
                logging.warning(f"현재 옵션: {current_option}")
                logging.warning(f"추가 옵션: {add_additional_options}")
                
                if add_additional_options:
                    # add_additional_options 메서드를 호출하여 추가 옵션 추가
                    order_manager.add_additional_options(drink, quantity, temperature, size, current_option, add_additional_options)
                else: 
                    # 추가라는 것을 받아들였을때 샷이 없을 경우에도 주문으로 처리 되도록
                    order_manager.add_order(drink, quantity, temperature, size, add_additional_options)

            # 최종 확인 메시지 생성 및 사용자에게 전달
            confirmation_message = f"말씀하신 옵션이 추가 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)
            return []

        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(text="추가 옵션 추가 중 문제가 발생했습니다. 다시 시도해 주세요.")
            logging.exception("Exception occurred in action_add_additional_option")
            return []
                   
# 커피 추가옵션 제거        
class ActionRemoveAdditionalOption(Action):
    def name(self) -> Text:
        return "action_remove_additional_option"
    
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:
            # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            # 엔티티를 정렬하고 매핑
            mapper = OrderMapper(entities)
            temperatures, drink_types, sizes, quantities, additional_options = mapper.get_mapped_data()

            # 디버깅을 위한 로그 출력
            logging.warning(f"추가 옵션 제거 입력 내용: {entities}")
            logging.warning(f"추가 옵션 제거 매핑 데이터: {temperatures, drink_types, sizes, quantities, additional_options}")

            raise_missing_attribute_error(mapper.drinks)  # 음료 속성 검증

            # 제거할 옵션이 없으면 사용자에게 메시지 출력하고 종료
            if not additional_options:
                dispatcher.utter_message(text="제거할 옵션을 지정해주세요.")
                return []

            # 매핑된 데이터를 사용하여 주문 정보 업데이트
            for i in range(len(drink_types)):
                drink = drink_types[i]  # 음료 종류
                quantity = quantities[i] if quantities[i] is not None else 1  # 잔 수
                temperature = temperatures[i] if i < len(temperatures) else "핫"  # 온도
                size = sizes[i] if i < len(sizes) else "미디움"  # 사이즈
                current_additional_option = additional_options[i] if i < len(additional_options) else None  # 현재 추가 옵션

                if current_additional_option:
                    # 현재 옵션에서 중복된 옵션 제거
                    current_options = list(set(current_additional_option.split(", ")))
                    last_remove_option = current_options[-1]  # 마지막 옵션을 제거할 옵션으로 설정

                    # 중복된 옵션이 있는지 확인 후 제거할 옵션 설정
                    for option in reversed(current_options):
                        if current_additional_option.count(option) > 1:
                            last_remove_option = option
                            break

                    logging.warning(f"제거해야할 옵션 : {last_remove_option}, 현재 주문되어 있는 옵션 : {current_options}")

                    order_manager.remove_additional_options(drink, quantity, temperature, size, current_options, last_remove_option)

            # 최종 확인 메시지 생성 및 사용자에게 전달
            confirmation_message = f"말씀하신 옵션이 제거 되었습니다. 주문하신 음료는 {order_manager.get_order_summary()}입니다. 다른 추가 옵션이 필요하신가요?"
            dispatcher.utter_message(text=confirmation_message)

            return []
        except Exception as e:
            # 예외 발생 시 사용자에게 메시지 전달
            dispatcher.utter_message(f"추가 옵션 제거 중 문제가 발생했습니다. 다시 시도해 주세요.")
            return []


# 주문 테이크아웃 판별
class ActionTakeOut(Action):
    def name(self) -> Text:
        return "action_takeout"

    # 주문을 완료하는 액션 실행
    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        try:          
            # 최신 사용자 메시지에서 DIETClassifier가 아닌 엔티티를 가져오기
            entities = [entity for entity in tracker.latest_message.get("entities", []) if entity.get("extractor") != "DIETClassifier"]
            
            manager = OrderManager()
            # 테이크 엔티티 확인
            logging.warning(f"테이크아웃 엔티티: {entities}")

            # x 값을 기준으로 엔티티 정렬
            sorted_entities = sorted(entities, key=lambda e: e.get("x", 0))

            # 'take' 엔티티 필터링
            take_entities = [entity for entity in sorted_entities if entity.get("entity") == "take"]

            if take_entities:
                if len(take_entities) == 1:
                    # 'take' 엔티티가 하나일 경우 그 값을 사용
                    last_take_value = take_entities[0].get("value")
                else:
                    # 'take' 엔티티가 여러 개일 경우 가장 마지막의 값 사용
                    last_take_value = take_entities[-1].get("value")

                # take 엔티티 표준화
                takeout = standardize_take(last_take_value)

                # 최종 주문 메시지 생성
                final_message = f"{takeout} 주문이 완료되었습니다. 결제는 하단의 카드리더기로 결제해 주시기 바랍니다. 감사합니다."
            # 메시지 출력
            dispatcher.utter_message(text=final_message)
            return []
        except Exception as e:
            # 오류 발생 시 예외 처리
            logging.exception("Exception occurred in action_order_finish")
            dispatcher.utter_message(text="결제 중 오류가 발생했습니다. 다시 시도해주세요.")
            return []
