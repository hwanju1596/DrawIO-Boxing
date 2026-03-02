import pdfplumber
import pandas as pd
import re
import glob
import os

def extract_all_pdfs(search_path=None):
    all_data = []
    
    # search_path가 주어지지 않으면 기본값 사용
    if not search_path:
        search_path = os.path.join("target", "table", "**", "*.pdf")
    
    pdf_files = glob.glob(search_path, recursive=True)
    
    if not pdf_files:
        print(f"PDF 파일을 찾을 수 없습니다. (경로: {search_path})")
        return

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"처리 중: {filename}")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                current_floor = ""
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if not tables:
                        continue
                    
                    for table in tables:
                        for row in table:
                            if not row: continue
                            
                            # 첫 번째 열에서 층 정보 업데이트 (B6, 1F 등 패턴 확인)
                            first_col = str(row[0]).strip() if row[0] else ""
                            if first_col and re.search(r'[A-Z0-9]+', first_col):
                                # 너무 긴 문장은 층 정보가 아닐 수 있음
                                if len(first_col) < 10:
                                    current_floor = first_col.replace("\n", "")
                            
                            # 모든 열을 순회하며 도어번호 패턴을 찾음
                            for cell in row:
                                if not cell: continue
                                cell_val = str(cell).strip().replace("\n", "")
                                
                                # 헤더 및 제외 단어
                                if any(x in cell_val for x in ["번호", "도어", "문", "REMARK", "HANDED", "H/W", "SET", "FSD"]):
                                    continue
                                    
                                # 도어번호 패턴: 알파벳+숫자가 섞이고 반드시 마침표(.)가 있는 것만 추출
                                codes = re.findall(r'[A-Z]+[0-9]*\.[0-9]+', cell_val)
                                
                                for code in codes:
                                    all_data.append({
                                        "파일명": filename,
                                        "층": current_floor,
                                        "도어번호": code
                                    })
        except Exception as e:
            print(f"오류 발생 ({filename}): {e}")

    # 데이터프레임 변환 및 저장
    if all_data:
        df = pd.DataFrame(all_data)
        
        # '층' 열이 비어있는 경우 바로 위의 값으로 채움
        import numpy as np
        df['층'] = df['층'].replace('', np.nan).ffill()
        
        output_file = os.path.join("target", "total_door_list.csv")
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n모든 파일 추출 완료: {output_file} (총 {len(df)}건)")
    else:
        print("추출된 데이터가 없습니다.")

if __name__ == "__main__":
    extract_all_pdfs()
