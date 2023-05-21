use MeshiReserve;
-- create table reserved(id varchar(30), date varchar(30), time varchar(30), place varchar(30), start int, end int, idwithrand varchar(30), accountid int, whoreserved varchar(255));
create table reserved(id varchar(30), date varchar(30), day varchar(10), time varchar(30), place varchar(30), start int, end int, idwithrand varchar(30));
-- create table que(date varchar(30), place int, start int, accountid int, whoqued varchar(255));
create table que(start int, place int, whoqued varchar(30));
