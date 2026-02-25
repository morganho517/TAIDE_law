import os
import json
import re
from docx import Document

folder_path = 'rawdata' 
output_folder = 'processed_data'

# Ensure the output folder exists
os.makedirs(output_folder, exist_ok=True)

def docx_to_deep_structured_json(folder):
    # 判斷大標題：一、 二、
    main_heading_pattern = re.compile(r'^[一二三四五六七八九十]+、')
    # 判斷小標題：(一) 或 （一） (支援全半形括號)
    sub_heading_pattern = re.compile(r'^[(（][一二三四五六七八九十]+[)）]')

    for filename in os.listdir(folder):
        if filename.endswith('.docx') and not filename.startswith('~'):
            doc_path = os.path.join(folder, filename)
            try:
                doc = Document(doc_path)
                
                document_data = {
                    "document_name": filename,
                    "sections": []
                }
                
                # 初始化當前大段落與小段落
                current_section = {"heading": "文件前言與大標", "sub_sections": []}
                current_sub_section = {"sub_heading": "本文", "content": []}
                
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                        
                    # 遇到大標題 (一、)
                    if main_heading_pattern.match(text):
                        # 先把舊的小段落收尾，裝進大段落
                        if current_sub_section["content"] or current_sub_section["sub_heading"] != "本文":
                            current_section["sub_sections"].append(current_sub_section)
                        # 把舊的大段落收尾，裝進整份文件
                        if current_section["sub_sections"] or current_section["heading"] != "文件前言與大標":
                            document_data["sections"].append(current_section)
                        
                        # 開啟新的大段落
                        current_section = {"heading": text, "sub_sections": []}
                        # 重置小段落
                        current_sub_section = {"sub_heading": "本文", "content": []}
                        
                    # 遇到小標題 ((一))
                    elif sub_heading_pattern.match(text):
                        # 把舊的小段落收尾，裝進當前的大段落裡
                        if current_sub_section["content"] or current_sub_section["sub_heading"] != "本文":
                            current_section["sub_sections"].append(current_sub_section)
                        
                        # 開啟新的小段落
                        current_sub_section = {"sub_heading": text, "content": []}
                        
                    # 一般內文
                    else:
                        current_sub_section["content"].append(text)
                
                # 迴圈結束，把最後殘留的段落全部收尾存好
                if current_sub_section["content"] or current_sub_section["sub_heading"] != "本文":
                    current_section["sub_sections"].append(current_sub_section)
                if current_section["sub_sections"] or current_section["heading"] != "文件前言與大標":
                    document_data["sections"].append(current_section)

                # 輸出 JSON
                json_filename = filename.replace('.docx', '.json')
                json_path = os.path.join(output_folder, json_filename)  # Updated to use output folder
                
                with open(json_path, 'w', encoding='utf-8') as json_file:
                    json.dump(document_data, json_file, ensure_ascii=False, indent=4)
                    
                print(f"✅ 成功深度結構化：{filename} -> {json_filename}")
                
            except Exception as e:
                print(f"❌ 轉換 {filename} 時發生錯誤：{e}")

if __name__ == "__main__":
    docx_to_deep_structured_json(folder_path)