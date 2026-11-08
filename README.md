# Urban Heat & Energy Burden (CS341 Term Project)

ระบบ Data Pipeline สำหรับวิเคราะห์ความสัมพันธ์ระหว่างความร้อนและภาระค่าใช้จ่ายด้านพลังงานของครัวเรือนในเขตเมือง (สำหรับส่งงานเฟส 2: Checkpoint - Working Critical-Path Pipeline)

## 📂 โครงสร้างโฟลเดอร์ (Project Structure)
โปรเจกต์นี้ใช้การจัดเก็บข้อมูลแบบ Medallion Architecture เพื่อให้ง่ายต่อการประมวลผลแบบ Local:

* `data/bronze/` : เก็บข้อมูลดิบ (Raw Data) ที่ดึงมาจากแหล่งต้นทาง
* `data/silver/` : เก็บข้อมูลที่ผ่านการทำความสะอาดและตรวจสอบคุณภาพ (Validated & Cleaned)
* `data/gold/` : เก็บข้อมูลที่ผ่านการ Join และพร้อมนำไปใช้วิเคราะห์ (Curated Data)
* `scripts/` : โฟลเดอร์สำหรับเก็บไฟล์สคริปต์ Python (`.py`) ของ Data Pipeline
* `notebooks/` : โฟลเดอร์สำหรับเก็บไฟล์ Jupyter Notebook สำหรับทำ EDA และสรุปผล
* `requirements.txt` : รายชื่อ Library ที่ต้องใช้ในโปรเจกต์

## 🚀 วิธีการติดตั้ง (Installation)

เพื่อให้ทุกคนในทีมมี Environment ที่ตรงกัน รบกวนทำตามขั้นตอนนี้:

1. **Clone Repository** มาที่เครื่องตัวเอง
   ```bash
   git clone [https://github.com/chaloemwong109-lab/urban-heat-energy-burden.git](https://github.com/chaloemwong109-lab/urban-heat-energy-burden.git)
   cd urban-heat-energy-burden