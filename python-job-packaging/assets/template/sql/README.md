# sql/

放 {{app}} 需要的 DDL、預建資料與權限範本。

規則（規範 §5、FAQ D1／D2）：

- **每句可獨立執行**：DBeaver 以分號拆句，變數宣告與使用會被拆到不同批次（`必須宣告資料表變數`）。
- Oracle 不寫 PL/SQL 區塊（DBeaver 會吃掉 `END;` 的分號），改用純 SQL，例如 `INSERT ... SELECT ... WHERE NOT EXISTS`。
- 可重複執行（先判斷存在再建立），不刪除既有資料。
- 權限範本只給最小權限：讀來源、寫目的表；不使用 sa／DBA 帳號。

TODO(專案)：加入建表與授權腳本，並在 `selfcheck.py` 的 `REQUIRED_*_TABLES` 列出這些表。
