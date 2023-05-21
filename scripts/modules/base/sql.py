import mysql.connector


class MeshiReserveDB:
    def __init__(
        self, host="mysql", database="MeshiReserve", user="root", password="root"
    ):
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


# retr_reserve_code + accountid + whoreseved で取得したリストを引数に取る
# 現在は、retr_reserve_code で取得したリストを引数に取る
def insert_reserve_data(reserve_data_list: list[str]):
    with MeshiReserveDB() as (cursor, cnx):
        # sql = """
        # insert into que
        #     (id, date, time, place, start, end, idwithrand, accountid, whoreserved)
        # values
        #     (%s, %s, %s, %s, %d, %d, %s, %d, %s)
        # """
        sql = """
        insert into reserved
            (id, date, time, place, start, end, idwithrand)
        values
            (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.executemany(sql, reserve_data_list)
        cnx.commit()


# def insert_reserve_que():


def select_by_date_from_reserved(date: str):
    with MeshiReserveDB() as (cursor, cnx):
        sql = """
        select * from reserved where date = %s
        """
        cursor.execute(sql, (date,))
        return cursor.fetchall()
