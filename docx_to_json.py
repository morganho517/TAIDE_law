import os
import json
from docx import Document

# 請將這裡替換成您存放 .docx 檔案的資料夾路徑
# 例如: folder_path = r"C:\Users\YourName\Desktop\MyDocs"
folder_path = "/home/morgan0429/Taide/1"

def docx_to_json(folder):
    # 尋找資料夾中的所有檔案
    for filename in os.listdir(folder):
        if filename.endswith('.docx') and not filename.startswith('~'): # 排除暫存檔
            doc_path = os.path.join(folder, filename)
            
            try:
                # 1. 讀取 Word 文件
                doc = Document(doc_path)
                paragraphs_text = []
                
                # 2. 擷取每個段落的文字 (自動過濾掉完全空白的行)
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if text:
                        paragraphs_text.append(text)
                
                # 3. 定義 JSON 格式的資料結構
                data = {
                    "document_name": filename,
                    "content": paragraphs_text
                }
                
                # 4. 準備輸出的 JSON 檔案路徑
                json_filename = filename.replace('.docx', '.json')
                json_path = os.path.join(folder, json_filename)
                
                # 5. 寫入 JSON 檔案
                with open(json_path, 'w', encoding='utf-8') as json_file:
                    json.dump(data, json_file, ensure_ascii=False, indent=4)
                    
                print(f"✅ 成功轉換：{filename} -> {json_filename}")
                
            except Exception as e:
                print(f"❌ 轉換 {filename} 時發生錯誤：{e}")

if __name__ == "__main__":
    docx_to_json(folder_path)