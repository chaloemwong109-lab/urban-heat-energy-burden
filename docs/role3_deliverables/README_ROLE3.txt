ROLE 3 — ANALYTICS & EVIDENCE

ไฟล์ที่อยู่ในโฟลเดอร์นี้เป็น deliverables ของสมาชิก Role 3 สำหรับ Q1/Q2

ไฟล์หลัก:
- Role3_Q1_Q2_Analysis.ipynb: Notebook สำหรับสร้างผลวิเคราะห์จากข้อมูลโครงการจริงใน data/bronze โดยเลือกคอลัมน์และ mapping ตาม scripts/01_ingest_validate_survey.py
- q1_housing_analysis.csv: ตารางสรุปลักษณะที่อยู่อาศัยและผลกระทบสุขภาพ
- q1_association_tests.csv: ผล Chi-square tests สำหรับตัวแปร Q1
- q2_income_analysis.csv: ผลสรุป Energy Burden และข้อจำกัดตามช่วงรายได้
- PNG: กราฟประกอบรายงาน

วิธีรัน:
1. เปิด Terminal ที่ root ของ Repository
2. ติดตั้ง dependencies: pip install -r requirements.txt
3. เปิด Notebook: docs/role3_deliverables/Role3_Q1_Q2_Analysis.ipynb
4. Run All

หมายเหตุ:
- ต้องมีไฟล์ data/bronze/ThaiCI_Household_Questionaire_anonymized.xlsx อยู่ใน Repository ตามเดิม
- Energy Burden เป็นค่าประมาณจาก midpoint mapping ของช่วงรายได้และช่วงค่าไฟ ไม่ใช่ยอดเงินจริง
- ข้อมูลตัวอย่าง 88 ครัวเรือนมาจากชุมชนเดียว ไม่ควรเหมารวมเป็นตัวแทนทั้งกรุงเทพฯ
- ไม่ใส่ household-level CSV เพื่อหลีกเลี่ยงการเผยแพร่ข้อมูลระดับระเบียนโดยไม่จำเป็น
- DOCX/PDF รายงานฉบับรวมและ Excel working file ไม่จำเป็นต้องเก็บซ้ำใน source repository
