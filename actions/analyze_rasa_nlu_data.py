import re
import yaml
import pandas as pd
from collections import defaultdict
import os

def extract_entities(text):
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
    return re.findall(pattern, text)

def analyze_nlu_data(file_path, target_intents):
    with open(file_path, 'r', encoding='utf-8') as file:
        nlu_data = yaml.safe_load(file)

    intent_entity_counts = {intent: defaultdict(lambda: defaultdict(int)) for intent in target_intents}
    total_examples = defaultdict(int)

    for item in nlu_data.get('nlu', []):
        if 'intent' in item and item['intent'] in target_intents and 'examples' in item:
            intent = item['intent']
            examples = item['examples'].split('\n')
            for example in examples:
                example = example.strip()
                if example:
                    total_examples[intent] += 1
                    entities = extract_entities(example)
                    for content, label in entities:
                        intent_entity_counts[intent][label][content] += 1

    return intent_entity_counts, total_examples

def create_excel_from_intent_entity_data(intent_entity_counts, total_examples, output_file):
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        all_data = []
        for intent, label_counts in intent_entity_counts.items():
            for label, content_counts in label_counts.items():
                for content, count in content_counts.items():
                    all_data.append({
                        '내용': content,
                        '인텐트': intent,
                        '라벨': label,                        
                        '개수': count,
                        '총 예시 문장 수': total_examples[intent]
                    })
        
        df = pd.DataFrame(all_data)
        df = df.sort_values(['인텐트', '라벨', '개수'], ascending=[True, True, False])
        df.to_excel(writer, sheet_name='라벨링 분석', index=False)

        # Summary sheet
        total_entities = sum(sum(len(content_counts) for content_counts in label_counts.values()) for label_counts in intent_entity_counts.values())
        summary_df = pd.DataFrame({
            '총 인텐트 수': [len(intent_entity_counts)],
            '총 고유 라벨 수': [len(set(label for label_counts in intent_entity_counts.values() for label in label_counts))],
            '총 고유 엔티티 수': [total_entities],
            '총 예시 문장 수': [sum(total_examples.values())]
        })
        summary_df.to_excel(writer, sheet_name='요약', index=False)

        # Adjust column widths
        for sheet in writer.sheets.values():
            for idx, col in enumerate(sheet.columns):
                max_length = max(len(str(cell.value)) for cell in col)
                sheet.column_dimensions[chr(65 + idx)].width = max_length + 2

    print(f"엑셀 파일이 생성되었습니다: {output_file}")

if __name__ == "__main__":
    
    # nlu 저장된 파일 위치 
    file_path = 'lgh/training/rasa_minsu/meta/data/nlu.yml'
    
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 엑셀 파일 이름 지정하는 부분
    output_file = os.path.join(script_dir, '7차_라벨링.xlsx')

    #nlu intents 적용 대상 
    target_intents = [
        "order_coffee", 
        "modify_order", 
        "cancel_order", 
        "check_order",
        "subtract_order",
        "add_subtract_order",
        "coffee_recommend_order",
        "select_size_order",
        "select_temperature_order",
        "additional_options_add_order",
        "additional_options_subtract_order",
        "takeout_check"
    ]

    print("데이터 분석 시작...")
    intent_entity_counts, total_examples = analyze_nlu_data(file_path, target_intents)
    print("데이터 분석 완료. 엑셀 파일 생성 중...")
    create_excel_from_intent_entity_data(intent_entity_counts, total_examples, output_file)