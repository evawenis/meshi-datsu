import mysql.connector


class DataBaseHandler:
    def __init__(self, host, database, user, password):
        self.host = host
        self.database = database
        self.user = user
        self.password = password

    def __enter__(self):
        self.cnx = mysql.connector.connect(
            user=self.user,
            password=self.password,
            host=self.host,
            database=self.database,
        )
        self.cursor = self.cnx.cursor()
        return self.cursor, self.cnx

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        if self.cnx is not None and self.cnx.is_connected():
            self.cnx.close()


class MeshiReserveDB(DataBaseHandler):
    def __init__(
        self, host="mysql", database="MeshiReserve", user="root", password="root"
    ):
        super().__init__(host, database, user, password)

    def __enter__(self):
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

    def commit(self):
        return self.cnx.commit()

    def execute(self, operation, params=None):
        return self.cursor.execute(operation, params)

    def executemany(self, operation, seq_of_params):
        return self.cursor.executemany(operation, seq_of_params)

    def fetchall(self):
        return self.cursor.fetchall()

    # 仮実装
    # slack の一時キューから SQL へ登録
    def insert_temp_to_que(self, user_id, temp_ques: list[int]):
        sql = """
        insert into que
            (start, place, whoqued)
        values
            (%s, %s, %s)
        """
        self.executemany(sql, [t + [user_id] for t in temp_ques])
        self.commit()

    # retr_reserve_code + accountid + whoreseved で取得したリストを引数に取る
    # 現在は、retr_reserve_code で取得したリストを引数に取る
    def insert_reserved_data(self, reserved_data_list: list[str]):
        # sql = """
        # insert into que
        #     (id, date, day, time, place, start, end, idwithrand, accountid, whoreserved)
        # values
        #     (%s, %s, %s, %s, %s, %s, %s, %s, %d, %s)
        # """
        sql = """
        insert into reserved
            (id, date, day, time, place, start, end, idwithrand)
        values
            (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.executemany(sql, reserved_data_list)
        self.commit()

    def select_all_reserved_data(self):
        self.execute("select * from reserved")
        return self.fetchall()

    def select_all_reserved_date_where_date(self, date: str):
        sql = """
        select * from reserved where date = %s
        """
        self.execute(sql, (date,))
        return self.fetchall()

    def select_all_que_where_slack_id(self, slack_id: str):
        sql = """
        select * from que where whoqued = %s
        """
        self.execute(sql, (slack_id,))
        return self.fetchall()

    # slack id を受け取り、そのユーザの予約キューをすべて削除する
    def delete_all_que_where_slack_id(self, slack_id: str):
        sql = """
        delete from que where whoqued = %s
        """
        self.execute(sql, (slack_id,))
        return self.commit()
