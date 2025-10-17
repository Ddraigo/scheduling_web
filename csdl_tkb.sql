USE master
GO
DROP DATABASE CSDL_TKB

CREATE DATABASE CSDL_TKB
GO

USE CSDL_TKB

GO

/* ===== Danh mục khoa ===== */
CREATE TABLE tb_KHOA(
    MaKhoa      VARCHAR(12)  NOT NULL PRIMARY KEY, -- VD: KHOA-001
    TenKhoa     NVARCHAR(200) NOT NULL
);

GO

/* ===== tb_BO_MON ===== */
CREATE TABLE tb_BO_MON(
    MaBoMon    VARCHAR(12)    NOT NULL PRIMARY KEY, --VD: BM-001-001 cú pháp BM-3 số cuối MaKhoa-001 cùng khoa thì 3 số cuối tăng dần
	MaKhoa     VARCHAR(12)    NOT NULL,
    TenBoMon   NVARCHAR(200)  NOT NULL,
    FOREIGN KEY (MaKhoa) REFERENCES tb_KHOA(MaKhoa)
);

GO

/* ===== Giảng viên ===== */
CREATE TABLE tb_GIANG_VIEN(
    MaGV    VARCHAR(12)    NOT NULL PRIMARY KEY, -- VD: GV001
	MaBoMon VARCHAR(12)    NOT NULL,
    TenGV   NVARCHAR(200)  NOT NULL,
    LoaiGV  NVARCHAR(100)  NULL,
    GhiChu  NVARCHAR(300)  NULL,
    Email   VARCHAR(200)   NULL,
	FOREIGN KEY (MaBoMon) REFERENCES tb_BO_MON(MaBoMon)
);

GO

CREATE TABLE tb_DUKIEN_DT(
	MaDuKienDT      VARCHAR(15) NOT NULL PRIMARY KEY, --VD: 2025-2026_HK1: NamHoc_HocKy
	NamHoc          VARCHAR(9) NULL, 
	HocKy           TINYINT NOT NULL, -- 1: HK1, 2: HK2, 3: HK Hè
	NgayBD          SMALLDATETIME    NULL,  
    NgayKT          SMALLDATETIME    NULL,  
	MoTaHocKy       NVARCHAR(100) NULL
);

GO

/* ===== Môn học ===== */
CREATE TABLE tb_MON_HOC (
	MaMonHoc VARCHAR(10) NOT NULL PRIMARY KEY, --VD: MH-0000001
	TenMonHoc NVARCHAR(200) NOT NULL,
	SoTinChi TINYINT NULL,
	SoTietLT TINYINT NULL,
	SoTietTH TINYINT NULL,
	SoTuan TINYINT NOT NULL DEFAULT 15
);

GO


/* ===== GV đủ điều kiện dạy môn ===== */
CREATE TABLE tb_GV_DAY_MON(
    MaMonHoc VARCHAR(10) NOT NULL, 
    MaGV     VARCHAR(12) NOT NULL,
    PRIMARY KEY (MaMonHoc, MaGV),
    FOREIGN KEY (MaMonHoc) REFERENCES tb_MON_HOC(MaMonHoc),
    FOREIGN KEY (MaGV)     REFERENCES tb_GIANG_VIEN(MaGV)
);
GO

SELECT * 
FROM tb_GV_DAY_MON a
JOIN tb_MON_HOC b ON a.MaMonHoc = b.MaMonHoc
JOIN tb_GIANG_VIEN c ON a.MaGV = c.MaGV
WHERE b.TenMonHoc = N'Nhập môn Mạng máy tính' OR  b.TenMonHoc = N'Công nghệ phần mềm'



/* ===== Bảng CA (khung thời gian của 1 ca) ===== */
CREATE TABLE tb_KHUNG_TG(
    MaKhungGio   TINYINT       NOT NULL PRIMARY KEY, --VD: Ca1
    TenCa        NVARCHAR(50)  NULL,                 -- vd: Ca 1, Ca 2
    GioBatDau    TIME(0)       NOT NULL,
    GioKetThuc   TIME(0)       NOT NULL,
    SoTiet       TINYINT       NOT NULL DEFAULT(3)

);
GO

/* ===== Slot thời gian (Thứ × Ca) ===== */
CREATE TABLE tb_TIME_SLOT(
    TimeSlotID  VARCHAR(10) PRIMARY KEY, --Thu2-Ca1
    Thu         TINYINT     NOT NULL CHECK (Thu BETWEEN 2 AND 8), -- 2..CN(8)
    Ca          TINYINT     NOT NULL CHECK (Ca BETWEEN 1 AND 5),
	FOREIGN KEY (Ca) REFERENCES dbo.tb_KHUNG_TG(MaKhungGio),
	UNIQUE(Thu, Ca)

);

GO

CREATE TABLE tb_PHONG_HOC(
	MaPhong     VARCHAR(12) NOT NULL PRIMARY KEY, --vd: A101, B001, C406
	LoaiPhong   NVARCHAR(100) NULL,
	SucChua     SMALLINT NULL,
	ThietBi     NVARCHAR(400) NULL,
	GhiChu      NVARCHAR(200) NULL
);

GO

/* Ràng buộc mềm có thể chỉnh trọng số*/
CREATE TABLE tb_RANG_BUOC_MEM (
    MaRangBuoc        VARCHAR(15)  NOT NULL PRIMARY KEY,  --VD: RBM-001 
    TenRangBuoc		  NVARCHAR(200) NOT NULL,
	MoTa              NVARCHAR(500) NULL,
	TrongSo			  FLOAT NOT NULL
);

GO

/* ===== Lớp môn học (section) mở theo kỳ =====*/
CREATE TABLE tb_LOP_MONHOC(
    MaLop          VARCHAR(12)   NOT NULL PRIMARY KEY, --VD LOP-00000001
    MaMonHoc       VARCHAR(10)   NOT NULL,
    Nhom_MH        TINYINT       NOT NULL,
    To_MH          TINYINT       NULL, 
    SoLuongSV      SMALLINT      NULL,
    HeDaoTao       NVARCHAR(200) NULL,
    NgonNgu		   NVARCHAR(50)  NULL,
	ThietBiYeuCau  NVARCHAR(400) DEFAULT NULL,
	SoCaTuan	   TINYINT       DEFAULT 1, 
    FOREIGN KEY (MaMonHoc)   REFERENCES tb_MON_HOC(MaMonHoc),
    UNIQUE(MaMonHoc, Nhom_MH, To_MH)
);
GO

/* Đợt xếp TKB */
CREATE TABLE tb_DOT_XEP (
    MaDot        VARCHAR(20)  NOT NULL PRIMARY KEY,   -- ví dụ: DOT1_2025-2026_HK1, DOT2_2025-2026_HK1
    MaDuKienDT   VARCHAR(15)  NOT NULL,               -- kỳ học gắn đợt
    TenDot       NVARCHAR(200) NULL, 
    TrangThai    VARCHAR(20)  NOT NULL DEFAULT 'DRAFT', -- DRAFT/RUNNING/LOCKED/PUBLISHED
    NgayTao      DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
    NgayKhoa     DATETIME2    NULL, --LookedAt
    FOREIGN KEY (MaDuKienDT) REFERENCES tb_DUKIEN_DT(MaDuKienDT)
	
);

GO


-- bảng tb_PHAN_CONG 
CREATE TABLE tb_PHAN_CONG (
    MaDot VARCHAR(20) NOT NULL,
    MaLop VARCHAR(12) NOT NULL,
    MaGV VARCHAR(12) NULL,
    PRIMARY KEY (MaDot, MaLop),
    FOREIGN KEY (MaDot) REFERENCES tb_DOT_XEP(MaDot),
    FOREIGN KEY (MaLop) REFERENCES tb_LOP_MONHOC(MaLop),
    FOREIGN KEY (MaGV) REFERENCES tb_GIANG_VIEN(MaGV)
);

GO

CREATE TABLE tb_RANG_BUOC_TRONG_DOT (
	MaDot          VARCHAR(20)  NOT NULL,
    MaRangBuoc     VARCHAR(15)  NOT NULL,  
    FOREIGN KEY (MaDot) REFERENCES tb_DOT_XEP(MaDot),
	FOREIGN KEY (MaRangBuoc) REFERENCES tb_RANG_BUOC_MEM(MaRangBuoc),
	PRIMARY KEY( MaDot, MaRangBuoc)
);
GO

CREATE TABLE tb_NGUYEN_VONG(
	MaGV     VARCHAR(12) NOT NULL,
	MaDot    VARCHAR(20)  NOT NULL,
	TimeSlotID VARCHAR(10) NOT NULL, 
	PRIMARY KEY (MaGV, MaDot, TimeSlotID),
	FOREIGN KEY (TimeSlotID) REFERENCES tb_TIME_SLOT(TimeSlotID),
	FOREIGN KEY (MaGV) REFERENCES tb_GIANG_VIEN(MaGV),
	FOREIGN KEY (MaDot) REFERENCES dbo.tb_DOT_XEP(MaDot)
);
GO

/* ===== Thời khoá biểu: thêm MaLop và loại bỏ NgayBD, NgayKT nếu không cần */
CREATE TABLE tb_TKB(
    MaTKB       VARCHAR(15)  NOT NULL PRIMARY KEY, 
	MaDot       VARCHAR(20) NOT NULL,
	MaLop		VARCHAR(12) NOT NULL,
    MaPhong     VARCHAR(12)  NOT NULL,
    TimeSlotID  VARCHAR(10)  NOT NULL, 
    TuanHoc     VARCHAR(64) NULL, -- VD: 2345678-01234567--------------------------
	NgayBD		SMALLDATETIME NULL,
	NgayKT		SMALLDATETIME NULL,

	UNIQUE (MaDot, MaLop, MaPhong, TimeSlotID),

    FOREIGN KEY (MaPhong) REFERENCES tb_PHONG_HOC(MaPhong),
	FOREIGN KEY (MaLop) REFERENCES tb_LOP_MONHOC(MaLop),
    FOREIGN KEY (TimeSlotID) REFERENCES tb_TIME_SLOT(TimeSlotID),
	FOREIGN KEY (MaDot) REFERENCES tb_DOT_XEP(MaDot)
);
GO

/* ===== Dữ liệu mẫu cho 5 ca (điển hình; chỉnh lại theo quy định của bạn) ===== */
INSERT INTO tb_KHUNG_TG(MaKhungGio, TenCa, GioBatDau, GioKetThuc, SoTiet)
SELECT v.MaKhungGio, v.TenCa, v.GioBD, v.GioKT, v.SoTiet
FROM (VALUES
    (1, N'Ca 1',  TIMEFROMPARTS(6,  50, 0, 0, 0), TIMEFROMPARTS(9,  20, 0, 0, 0), 3),
    (2, N'Ca 2',  TIMEFROMPARTS(9,  30, 0, 0, 0), TIMEFROMPARTS(12, 0, 0, 0, 0), 3),
    (3, N'Ca 3', TIMEFROMPARTS(12, 45, 0, 0, 0), TIMEFROMPARTS(15, 15,  0, 0, 0), 3),
    (4, N'Ca 4', TIMEFROMPARTS(15, 25, 0, 0, 0), TIMEFROMPARTS(17, 55, 0, 0, 0), 3),
    (5, N'Ca 5',     TIMEFROMPARTS(18, 05,  0, 0, 0), TIMEFROMPARTS(20, 35, 0, 0, 0), 3)
) AS v(MaKhungGio, TenCa, GioBD, GioKT, SoTiet)
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_KHUNG_TG c WHERE c.MaKhungGio = v.MaKhungGio);

GO

-- Tạo đầy đủ TimeSlotID : Thu2..Thu7 và CN; Ca 1..5
INSERT INTO tb_TIME_SLOT (TimeSlotID, Thu, Ca)
SELECT
    CASE WHEN d.Thu = 8
         THEN CONCAT('CN-Ca', c.Ca)
         ELSE CONCAT('Thu', d.Thu, '-Ca', c.Ca)
    END AS TimeSlotID,
    d.Thu,
    c.Ca
FROM (VALUES (2),(3),(4),(5),(6),(7),(8)) AS d(Thu)
CROSS JOIN (VALUES (1),(2),(3),(4),(5))   AS c(Ca)
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.tb_TIME_SLOT t
    WHERE t.Thu = d.Thu AND t.Ca = c.Ca
);


-- Kiểm tra nhanh
SELECT COUNT(*) AS SoDong, MIN(TimeSlotID) AS MinID, MAX(TimeSlotID) AS MaxID
FROM dbo.tb_TIME_SLOT;

SELECT * FROM dbo.tb_TIME_SLOT;

SELECT 
    ts.TimeSlotID, ts.Thu, ts.Ca, kh.TenCa,
    LEFT(CONVERT(varchar(8), kh.GioBatDau, 108), 5) AS GioBD,
    LEFT(CONVERT(varchar(8), kh.GioKetThuc,108), 5) AS GioKT,
    CONCAT(LEFT(CONVERT(varchar(8), kh.GioBatDau,108),5),' - ',
           LEFT(CONVERT(varchar(8), kh.GioKetThuc,108),5)) AS GioHoc
FROM dbo.tb_TIME_SLOT ts
JOIN dbo.tb_KHUNG_TG kh ON kh.MaKhungGio = ts.Ca
ORDER BY ts.Thu, ts.Ca;

GO

/* ===== Khoa/Bộ môn/Giảng viên ===== */
-- Email có thể rỗng, nếu có thì không được trùng
CREATE UNIQUE INDEX UX_GV_Email_NotNull ON dbo.tb_GIANG_VIEN(Email) WHERE Email IS NOT NULL;

-- Bộ môn không trùng tên trong cùng Khoa
ALTER TABLE tb_BO_MON ADD CONSTRAINT UQ_BM_Ten_Trong_Khoa UNIQUE(MaKhoa, TenBoMon);

/* ===== Môn học ===== */
ALTER TABLE tb_MON_HOC ADD CONSTRAINT CK_MON_SoTinChi_Pos   CHECK (SoTinChi IS NULL OR SoTinChi >=1);
ALTER TABLE tb_MON_HOC ADD CONSTRAINT CK_MON_SoTietLT_Pos   CHECK (SoTietLT IS NULL OR SoTietLT >= 0);
ALTER TABLE tb_MON_HOC ADD CONSTRAINT CK_MON_SoTietTH_Pos   CHECK (SoTietTH IS NULL OR SoTietTH >= 0);
ALTER TABLE tb_MON_HOC ADD CONSTRAINT CK_MON_SoTuan_Range   CHECK (SoTuan > 0);

/* ===== Lớp môn học ===== */
ALTER TABLE tb_LOP_MONHOC ADD CONSTRAINT CK_LMH_Nhom_Pos    CHECK (Nhom_MH >= 1);
ALTER TABLE tb_LOP_MONHOC ADD CONSTRAINT CK_LMH_To_Pos      CHECK (To_MH IS NULL OR To_MH >= 0);
ALTER TABLE tb_LOP_MONHOC ADD CONSTRAINT CK_LMH_SoLuong_Pos CHECK (SoLuongSV IS NULL OR SoLuongSV >= 0);
ALTER TABLE tb_LOP_MONHOC ADD CONSTRAINT CK_LMH_SoCaTuan    CHECK (SoCaTuan BETWEEN 1 AND 5);

/* ===== Phòng học ===== */
ALTER TABLE tb_PHONG_HOC ADD CONSTRAINT CK_PH_SucChua_Pos   CHECK (SucChua IS NULL OR SucChua > 0);

/* ===== Khung giờ/Timeslot ===== */
ALTER TABLE tb_KHUNG_TG ADD CONSTRAINT CK_KTG_ThoiGian_Valid CHECK (GioBatDau < GioKetThuc AND SoTiet >= 1);

/* ===== Dự kiến đào tạo/Đợt xếp ===== */
ALTER TABLE tb_DUKIEN_DT ADD CONSTRAINT CK_DK_HocKy CHECK (HocKy IN (1,2,3,4));
ALTER TABLE tb_DUKIEN_DT ADD CONSTRAINT CK_DK_NgayBD_KT CHECK (NgayBD IS NULL OR NgayKT IS NULL OR NgayBD <= NgayKT);

ALTER TABLE tb_DOT_XEP ADD CONSTRAINT CK_DOT_TrangThai CHECK (TrangThai IN ('DRAFT','RUNNING','LOCKED','PUBLISHED'));


CREATE INDEX IX_GV_MaBoMon     ON tb_GIANG_VIEN(MaBoMon);
CREATE INDEX IX_BM_MaKhoa      ON tb_BO_MON(MaKhoa);
CREATE INDEX IX_PC_MaGV        ON tb_PHAN_CONG(MaGV);
CREATE INDEX IX_PC_MaLop       ON tb_PHAN_CONG(MaLop);
CREATE INDEX IX_PC_MaDot       ON tb_PHAN_CONG(MaDot);
CREATE INDEX IX_TKB_MaDot      ON tb_TKB(MaDot);
CREATE INDEX IX_TKB_MaLop	   ON tb_TKB(MaLop);
CREATE INDEX IX_TKB_TimeSlotID ON tb_TKB(TimeSlotID);
CREATE INDEX IX_LMH_MaMonHoc   ON tb_LOP_MONHOC(MaMonHoc);

GO

SELECT TOP 10 MaLop, SoCaTuan FROM tb_LOP_MONHOC


-------------------INSERT DATA-----------------

INSERT INTO dbo.tb_KHOA (MaKhoa, TenKhoa)
VALUES ('KHOA-001', N'Khoa Công nghệ thông tin'),
       ('KHOA-002', N'Khoa Điện - Điện tử'),
       ('KHOA-003', N'Khoa quản trị kinh doanh');


GO



INSERT INTO tb_BO_MON (MaBoMon, MaKhoa, TenBoMon)
VALUES
-- KHOA-001 (CNTT) - 4 bộ môn
('BM-001-001','KHOA-001',N'Bộ môn Khoa học Máy tính'),
('BM-001-002','KHOA-001',N'Bộ môn Hệ thống Thông tin'),
('BM-001-003','KHOA-001',N'Bộ môn Mạng & An ninh'),
('BM-001-004','KHOA-001',N'Bộ môn Kỹ thuật phần mềm'),

-- KHOA-002 (Điện - Điện tử) - 3 bộ môn
('BM-002-001','KHOA-002',N'Bộ môn Điện tử'),
('BM-002-002','KHOA-002',N'Bộ môn Hệ thống Điện'),
('BM-002-003','KHOA-002',N'Bộ môn Tự động hóa'),

-- KHOA-003 (Kinh tế) - 3 bộ môn
('BM-003-001','KHOA-003',N'Bộ môn Kế toán'),
('BM-003-002','KHOA-003',N'Bộ môn Tài chính'),
('BM-003-003','KHOA-003',N'Bộ môn Quản trị');


GO


INSERT INTO tb_GIANG_VIEN (MaGV, MaBoMon, TenGV, LoaiGV, GhiChu, Email)
VALUES
-- KHOA-001
('GV001','BM-001-001',N'Nguyễn Minh An',       N'Cơ hữu',       NULL,'gv001@univ.edu.vn'),
('GV002','BM-001-001',N'Trần Quang Huy',       N'Thỉnh giảng',  NULL,'gv002@univ.edu.vn'),

('GV003','BM-001-002',N'Lê Thị Mai',           N'Cơ hữu',       NULL,'gv003@univ.edu.vn'),
('GV004','BM-001-002',N'Phạm Văn Khánh',       N'Thỉnh giảng',  NULL,'gv004@univ.edu.vn'),

('GV005','BM-001-003',N'Hoàng Đức Long',       N'Cơ hữu',       NULL,'gv005@univ.edu.vn'),
('GV006','BM-001-003',N'Phan Ngọc Bích',       N'Thỉnh giảng',  NULL,'gv006@univ.edu.vn'),

('GV007','BM-001-004',N'Vũ Hải Nam',           N'Cơ hữu',       NULL,'gv007@univ.edu.vn'),
('GV008','BM-001-004',N'Đặng Thu Trang',       N'Thỉnh giảng',  NULL,'gv008@univ.edu.vn'),

-- BM-001-001
('GV009','BM-001-001',N'Ngô Văn Bình',        N'Cơ hữu',       NULL,'gv009@univ.edu.vn'),
('GV010','BM-001-001',N'Bùi Anh Tuấn',        N'Thỉnh giảng',  NULL,'gv010@univ.edu.vn'),
('GV011','BM-001-001',N'Đỗ Phương Linh',      N'Cơ hữu',       NULL,'gv011@univ.edu.vn'),
('GV012','BM-001-001',N'Hồ Thanh Tùng',       N'Thỉnh giảng',  NULL,'gv012@univ.edu.vn'),
('GV013','BM-001-001',N'Ngô Thảo My',         N'Cơ hữu',       NULL,'gv013@univ.edu.vn'),
('GV014','BM-001-001',N'Dương Quốc Khánh',    N'Thỉnh giảng',  NULL,'gv014@univ.edu.vn'),
('GV015','BM-001-001',N'Phạm Thu Hà',         N'Cơ hữu',       NULL,'gv015@univ.edu.vn'),
('GV016','BM-001-001',N'Vũ Minh Đức',         N'Thỉnh giảng',  NULL,'gv016@univ.edu.vn'),
('GV017','BM-001-001',N'Nguyễn Ngọc Ánh',     N'Cơ hữu',       NULL,'gv017@univ.edu.vn'),
('GV018','BM-001-001',N'Trịnh Văn Lợi',       N'Thỉnh giảng',  NULL,'gv018@univ.edu.vn'),

-- BM-001-002
('GV019','BM-001-002',N'Phan Hữu Nghĩa',      N'Cơ hữu',       NULL,'gv019@univ.edu.vn'),
('GV020','BM-001-002',N'Đặng Hoài Nam',       N'Thỉnh giảng',  NULL,'gv020@univ.edu.vn'),
('GV021','BM-001-002',N'Nguyễn Thuỳ Dương',   N'Cơ hữu',       NULL,'gv021@univ.edu.vn'),
('GV022','BM-001-002',N'Lê Hồng Sơn',         N'Thỉnh giảng',  NULL,'gv022@univ.edu.vn'),
('GV023','BM-001-002',N'Tạ Bảo Châu',         N'Cơ hữu',       NULL,'gv023@univ.edu.vn'),
('GV024','BM-001-002',N'Vũ Quang Hảo',        N'Thỉnh giảng',  NULL,'gv024@univ.edu.vn'),
('GV025','BM-001-002',N'Hoàng Minh Khang',    N'Cơ hữu',       NULL,'gv025@univ.edu.vn'),
('GV026','BM-001-002',N'Phạm Thị Yến',        N'Thỉnh giảng',  NULL,'gv026@univ.edu.vn'),
('GV027','BM-001-002',N'Nguyễn Quốc Huy',     N'Cơ hữu',       NULL,'gv027@univ.edu.vn'),
('GV028','BM-001-002',N'Lưu Trọng Tín',       N'Thỉnh giảng',  NULL,'gv028@univ.edu.vn'),

-- BM-001-003
('GV029','BM-001-003',N'Vũ Thị Hạnh',         N'Cơ hữu',       NULL,'gv029@univ.edu.vn'),
('GV030','BM-001-003',N'Nguyễn Đức Cường',    N'Thỉnh giảng',  NULL,'gv030@univ.edu.vn'),
('GV031','BM-001-003',N'Lê Minh Hiếu',        N'Cơ hữu',       NULL,'gv031@univ.edu.vn'),
('GV032','BM-001-003',N'Phạm Ngọc Anh',       N'Thỉnh giảng',  NULL,'gv032@univ.edu.vn'),
('GV033','BM-001-003',N'Đào Khánh Linh',      N'Cơ hữu',       NULL,'gv033@univ.edu.vn'),
('GV034','BM-001-003',N'Trần Hải Yến',        N'Thỉnh giảng',  NULL,'gv034@univ.edu.vn'),
('GV035','BM-001-003',N'Hoàng Gia Bảo',       N'Cơ hữu',       NULL,'gv035@univ.edu.vn'),
('GV036','BM-001-003',N'Nguyễn Trọng Tài',    N'Thỉnh giảng',  NULL,'gv036@univ.edu.vn'),
('GV037','BM-001-003',N'Bùi Minh Châu',       N'Cơ hữu',       NULL,'gv037@univ.edu.vn'),
('GV038','BM-001-003',N'Phan Quốc Việt',      N'Thỉnh giảng',  NULL,'gv038@univ.edu.vn'),

-- BM-001-004
('GV039','BM-001-004',N'Đỗ Ngọc Diệp',        N'Cơ hữu',       NULL,'gv039@univ.edu.vn'),
('GV040','BM-001-004',N'Tạ Minh Tuấn',        N'Thỉnh giảng',  NULL,'gv040@univ.edu.vn'),
('GV041','BM-001-004',N'Nguyễn Thị Hương',    N'Cơ hữu',       NULL,'gv041@univ.edu.vn'),
('GV042','BM-001-004',N'Lý Tuấn Kiệt',        N'Thỉnh giảng',  NULL,'gv042@univ.edu.vn'),
('GV043','BM-001-004',N'Vũ Đức Thịnh',        N'Cơ hữu',       NULL,'gv043@univ.edu.vn'),
('GV044','BM-001-004',N'Phạm Thuỷ Tiên',      N'Thỉnh giảng',  NULL,'gv044@univ.edu.vn'),
('GV045','BM-001-004',N'Trương Mạnh Hùng',    N'Cơ hữu',       NULL,'gv045@univ.edu.vn'),
('GV046','BM-001-004',N'Đoàn Khánh Vy',       N'Thỉnh giảng',  NULL,'gv046@univ.edu.vn'),
('GV047','BM-001-004',N'Trần Đức Long',       N'Cơ hữu',       NULL,'gv047@univ.edu.vn'),
('GV048','BM-001-004',N'Nguyễn Thảo Nguyên',  N'Thỉnh giảng',  NULL,'gv048@univ.edu.vn'),

-- KHOA-002
('GV0049','BM-002-001',N'Bùi Anh Tuấn',         N'Cơ hữu',       NULL,'gv049@univ.edu.vn'),
('GV050','BM-002-001',N'Đỗ Phương Linh',       N'Thỉnh giảng',  NULL,'gv050@univ.edu.vn'),

('GV051','BM-002-002',N'Hồ Thanh Tùng',        N'Cơ hữu',       NULL,'gv051@univ.edu.vn'),
('GV052','BM-002-002',N'Ngô Thảo My',          N'Thỉnh giảng',  NULL,'gv052@univ.edu.vn'),

('GV053','BM-002-003',N'Dương Quốc Khánh',     N'Cơ hữu',       NULL,'gv053@univ.edu.vn'),
('GV054','BM-002-003',N'Đinh Kim Oanh',        N'Thỉnh giảng',  NULL,'gv054@univ.edu.vn'),

-- KHOA-003
('GV055','BM-003-001',N'Trương Hoài Nam',      N'Cơ hữu',       NULL,'gv055@univ.edu.vn'),
('GV056','BM-003-001',N'Tạ Thu Hiền',          N'Thỉnh giảng',  NULL,'gv056@univ.edu.vn'),

('GV057','BM-003-002',N'Mai Đức Phong',        N'Cơ hữu',       NULL,'gv057@univ.edu.vn'),
('GV058','BM-003-002',N'Võ Ngọc Ánh',          N'Thỉnh giảng',  NULL,'gv058@univ.edu.vn'),

('GV059','BM-003-003',N'Huỳnh Gia Bảo',        N'Cơ hữu',       NULL,'gv059@univ.edu.vn'),
('GV060','BM-003-003',N'Lâm Khánh Vy',         N'Thỉnh giảng',  NULL,'gv060@univ.edu.vn');


GO


INSERT INTO tb_DUKIEN_DT (MaDuKienDT, NamHoc, HocKy, NgayBD, NgayKT, MoTaHocKy)
VALUES
('2025-2026_HK1', '2025-2026', 1, '2025-09-01', '2026-01-15', N'Học kỳ 1 năm học 2025-2026'),
('2025-2026_HK2', '2025-2026', 2, '2026-02-15', '2026-06-30', N'Học kỳ 2 năm học 2025-2026');


GO


INSERT INTO tb_MON_HOC (MaMonHoc, TenMonHoc, SoTinChi, SoTietLT, SoTietTH, SoTuan)
VALUES
('502045',  N'Công nghệ phần mềm',                                                4, 45, 30, 15),
('502046',  N'Nhập môn Mạng máy tính',                                            4, 45, 30, 15),
('502047',  N'Nhập môn hệ điều hành',                                             4, 45, 30, 15),
('502049',  N'Nhập môn Bảo mật thông tin',                                        3, 45,  0, 15),
('502051',  N'Hệ cơ sở dữ liệu',                                                  4, 45, 30, 15),
('502052',  N'Phát triển hệ thống thông tin doanh nghiệp',                        3, 30, 30, 15),
('502061',  N'Xác suất và thống kê ứng dụng cho Công nghệ thông tin',            4, 45, 30, 15),
('502066',  N'Quản trị hệ thống mạng',                                            3, 30, 30, 15),
('502068',  N'IoT cơ bản',                                                        3, 30, 30, 15),
('502070',  N'Phát triển ứng dụng web với NodeJS',                                3, 30, 30, 15),

('50209260',N'Nhập môn Bảo mật thông tin',                                        3, 45,  0, 15),
('503040',  N'Phân tích và thiết kế giải thuật',                                  4, 45, 30, 15),
('503044',  N'Nhập môn Học máy',                                                  3, 45,  0, 15),
('503074',  N'Phát triển ứng dụng di động',                                       3, 30, 30, 15),
('503080',  N'Nhập môn thị giác máy tính',                                        3, 45,  0, 15),
('50308160',N'Nhập môn học máy',                                                  3, 45,  0, 15),
('503109',  N'Quản trị hệ thống thông tin',                                       3, 45,  0, 15),
('503110',  N'Thiết kế mạng',                                                     3, 30, 30, 15),
('503111',  N'Công nghệ Java',                                                    3, 30, 30, 15),
('503112',  N'Công nghệ .Net',                                                    3, 30, 30, 15),

('504008',  N'Cấu trúc dữ liệu và giải thuật',                                    4, 45, 30, 15),
('504045',  N'Nhập môn xử lý ngôn ngữ tự nhiên',                                  3, 45,  0, 15),
('504048',  N'Xử lý dữ liệu lớn',                                                 3, 45,  0, 15),
('504049',  N'Hệ thống thương mại thông minh',                                    3, 45,  0, 15),
('504087',  N'Điện toán đám mây',                                                 3, 30, 30, 15),
('504088',  N'Nhập môn Bảo mật máy tính',                                         3, 30, 30, 15),
('504091',  N'Dự án Công nghệ thông tin',                                         3,  0, 90, 15),
('50409660',N'Xử lý dữ liệu lớn',                                                 3, 45,  0, 15),
('50409760',N'Nhập môn xử lý ngôn ngữ tự nhiên',                                  3, 45,  0, 15),

('505041',  N'Nhập môn xử lý tiếng nói',                                          3, 45,  0, 15),
('505043',  N'Khai thác dữ liệu và Khai phá tri thức',                            3, 45,  0, 15),
('505060',  N'Nhập môn Xử lý ảnh số',                                             3, 30, 30, 15),
('50506960',N'Nhập môn Xử lý ảnh số',                                             3, 45,  0, 15),

/* Các bản tiếng Anh: dùng mã riêng EN để không trùng PK */
('502046EN',N'Nhập môn Mạng máy tính (Eng)',                                      4, 45, 30, 15),
('502051EN',N'Hệ cơ sở dữ liệu (Eng)',                                            4, 45, 30, 15),
('502061EN',N'Xác suất và thống kê ứng dụng cho Công nghệ thông tin (Eng)',       4, 45, 30, 15),

('502050',  N'Phân tích và thiết kế yêu cầu',                                     3, 45,  0, 15),
('502071',  N'Phát triển ứng dụng di động đa nền tảng',                           3, 30, 30, 15),
('503005',  N'Lập trình hướng đối tượng',                                         4, 45, 30, 15),
('503066',  N'Hệ thống hoạch định nguồn lực doanh nghiệp',                        3, 45,  0, 15),
('503107',  N'Phát triển ứng dụng di động nâng cao',                              3, 30, 30, 15),
('503108',  N'Thiết kế giao diện người dùng',                                     3, 30, 30, 15),
('503116',  N'Nhập môn Tư duy Logic',                                             3, 45,  0, 15),
('504074',  N'Kiến tập công nghiệp',                                              4,  0,120, 15),
('504075',  N'Dự án Công nghệ thông tin 2',                                       3,  0, 90, 15),
('504076',  N'Phát triển trò chơi',                                               3, 30, 30, 15),
('505010',  N'Kỹ năng soạn thảo văn bản kỹ thuật',                                1, 15,  0, 15),
('505011',  N'Lập trình hàm',                                                     3, 30, 30, 15);


GO


INSERT INTO dbo.tb_GV_DAY_MON (MaMonHoc, MaGV) VALUES
-- 1) Nhóm SE / LT cơ sở
('502045','GV001'),('502045','GV003'),('502045','GV009'),

('503005','GV001'),('503005','GV003'),('503005','GV011'),
('503040','GV001'),('503040','GV003'),('503040','GV009'),
('504008','GV001'),('504008','GV002'),('504008','GV003'),

-- 2) Mạng & Hệ điều hành
('502046','GV005'),('502046','GV006'),('502046','GV010'),
('502046EN','GV005'),('502046EN','GV006'),('502046EN','GV016'),
('503110','GV005'),('503110','GV006'),('503110','GV020'),

('502047','GV005'),('502047','GV001'),('502047','GV030'),
('502066','GV005'),('502066','GV006'),('502066','GV020'),
('503109','GV003'),('503109','GV004'),('503109','GV021'),

-- 3) Cơ sở dữ liệu & HTTT
('502051','GV003'),('502051','GV004'),('502051','GV011'),
('502051EN','GV003'),('502051EN','GV004'),('502051EN','GV023'),
('502052','GV003'),('502052','GV021'),('502052','GV025'),
('502050','GV003'),('502050','GV004'),('502050','GV021'),

-- 4) Xác suất – Thống kê
('502061','GV015'),('502061','GV017'),('502061','GV031'),
('502061EN','GV015'),('502061EN','GV017'),('502061EN','GV031'),

-- 5) An toàn thông tin / Bảo mật
('502049','GV005'),('502049','GV006'),('502049','GV024'),
('50209260','GV005'),('50209260','GV006'),('50209260','GV044'),
('504088','GV005'),('504088','GV006'),('504088','GV024'),

-- 6) IoT / Cloud / Hệ thống thương mại
('502068','GV040'),('502068','GV043'),('502068','GV045'),
('504087','GV004'),('504087','GV005'),('504087','GV040'),
('504049','GV004'),('504049','GV043'),('504049','GV045'),

-- 7) Lập trình Web / NodeJS / Java / .Net
('502070','GV003'),('502070','GV013'),('502070','GV047'),
('503111','GV003'),('503111','GV014'),('503111','GV047'),
('503112','GV003'),('503112','GV012'),('503112','GV047'),

-- 8) AI/ML, CV, NLP, Data Mining
('503044','GV007'),('503044','GV008'),('503044','GV033'),
('50308160','GV007'),('50308160','GV033'),('50308160','GV036'),
('503080','GV007'),('503080','GV008'),('503080','GV038'),
('505060','GV007'),('505060','GV008'),('505060','GV038'),
('50506960','GV007'),('50506960','GV038'),('50506960','GV035'),

('504045','GV033'),('504045','GV037'),('504045','GV041'),
('50409760','GV033'),('50409760','GV037'),('50409760','GV041'),

('505043','GV033'),('505043','GV035'),('505043','GV043'),
('504048','GV033'),('504048','GV035'),('504048','GV043'),
('50409660','GV033'),('50409660','GV035'),('50409660','GV043'),

-- 9) Mobile / Cross-platform / Advanced
('503074','GV001'),('503074','GV003'),('503074','GV037'),
('502071','GV001'),('502071','GV003'),('502071','GV037'),
('503107','GV001'),('503107','GV003'),('503107','GV037'),

-- 10) Dự án, kiến tập, kỹ năng
('504091','GV001'),('504091','GV003'),('504091','GV004'),
('504075','GV001'),('504075','GV003'),('504075','GV004'),
('504074','GV001'),('504074','GV003'),('504074','GV004'),
('505010','GV015'),('505010','GV013'),('505010','GV041'),

-- 11) Giao diện người dùng, logic, trò chơi
('503108','GV013'),('503108','GV041'),('503108','GV047'),
('503116','GV031'),('503116','GV017'),('503116','GV013'),
('504076','GV003'),('504076','GV001'),('504076','GV047'),

-- 12) Môn bổ sung còn lại
('503112','GV008'),('503112','GV013'),('503112','GV048');


GO


------THEM PHONG HOC------------
;WITH F AS (
    SELECT v AS Tang FROM (VALUES(4),(5),(6),(7)) X(v)
),
R AS (
    SELECT v AS Phong FROM (VALUES(1),(2),(3),(4),(5),(6),(7),(8),(9)) Y(v)
),
Gen AS (
    SELECT 
        MaPhong   = CONCAT('A', Tang, RIGHT('00' + CAST(Phong AS VARCHAR(2)), 2)), -- A401..A409, A501..A509...
        LoaiPhong = N'Thực hành',          -- tất cả là phòng thực hành
        SucChua   = 40,             -- bạn có thể đổi nếu cần
        ThietBi   = N'PC',          -- thiết bị mặc định PC
        GhiChu    = NULL
    FROM F CROSS JOIN R
)
INSERT INTO dbo.tb_PHONG_HOC (MaPhong, LoaiPhong, SucChua, ThietBi, GhiChu)
SELECT g.MaPhong, g.LoaiPhong, g.SucChua, g.ThietBi, g.GhiChu
FROM Gen g
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_PHONG_HOC x WHERE x.MaPhong = g.MaPhong);


GO


;WITH F AS (
    SELECT v AS Tang FROM (VALUES(2),(3),(4)) X(v)
),
R AS (
    SELECT v AS Phong FROM (VALUES(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11)) Y(v)
),
Gen AS (
    SELECT 
        MaPhong   = CONCAT('C', Tang, RIGHT('00' + CAST(Phong AS VARCHAR(2)), 2)), 
        LoaiPhong = N'Lý thuyết',     
        SucChua   = CASE WHEN Phong IN (1,6,7,9) THEN 90 ELSE 45 END,     
        ThietBi   = N'Máy chiếu, TV, máy lạnh, quạt',     
        GhiChu    = NULL
    FROM F CROSS JOIN R
)
INSERT INTO dbo.tb_PHONG_HOC (MaPhong, LoaiPhong, SucChua, ThietBi, GhiChu)
SELECT g.MaPhong, g.LoaiPhong, g.SucChua, g.ThietBi, g.GhiChu
FROM Gen g
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_PHONG_HOC x WHERE x.MaPhong = g.MaPhong);


GO


;WITH F AS (
    SELECT v AS Tang FROM (VALUES(2),(3),(4)) X(v)
),
R AS (
    SELECT v AS Phong FROM (VALUES(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11)) Y(v)
),
Gen AS (
    SELECT 
        MaPhong   = CONCAT('B', Tang, RIGHT('00' + CAST(Phong AS VARCHAR(2)), 2)), -- B201..B211, B301..B311, B401..B411
        LoaiPhong =  N'Thực hành',       -- đổi thành N'TH' nếu muốn
        SucChua   = CASE 
                        WHEN Phong IN (1,6,7,8,9) THEN 90           -- phòng lớn
                        ELSE 45                                   -- còn lại
                    END,
        ThietBi   = N'Máy chiếu, máy lạnh, TV',      
        GhiChu    = NULL
    FROM F CROSS JOIN R
)
INSERT INTO dbo.tb_PHONG_HOC (MaPhong, LoaiPhong, SucChua, ThietBi, GhiChu)
SELECT g.MaPhong, g.LoaiPhong, g.SucChua, g.ThietBi, g.GhiChu
FROM Gen g
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_PHONG_HOC x WHERE x.MaPhong = g.MaPhong);


GO


;WITH F AS (
    SELECT v AS Tang FROM (VALUES(1),(2),(3),(4)) X(v)
),
R AS (
    SELECT v AS Phong FROM (VALUES(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11)) Y(v)
),
Gen AS (
    SELECT 
        MaPhong   = CONCAT('D', Tang, RIGHT('00' + CAST(Phong AS VARCHAR(2)), 2)), -- D101..D111, D201..D211, D301..D311, D401..D411
        LoaiPhong = CASE 
                        WHEN Phong IN (8,11) THEN N'Thực hành'           -- thực hành
                        ELSE N'Lý thuyết'                                 -- mặc định lý thuyết; gồm cả 1,6,7,9
                    END,
        SucChua   = CASE 
                        WHEN Phong IN (1,6,7,8,9) THEN 90           -- phòng lớn
                        ELSE 45                                   -- còn lại
                    END,
        ThietBi   = CASE 
                        WHEN Phong IN (3,4,5)   THEN N'Thiết bị về điện'
                        WHEN Phong IN (1,2,6,7,8,9,10,11)    THEN N'Máy chiếu, TV, máy lạnh, quạt'
                        ELSE NULL
                    END,
        GhiChu    = NULL
    FROM F CROSS JOIN R
)
INSERT INTO dbo.tb_PHONG_HOC (MaPhong, LoaiPhong, SucChua, ThietBi, GhiChu)
SELECT g.MaPhong, g.LoaiPhong, g.SucChua, g.ThietBi, g.GhiChu
FROM Gen g
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_PHONG_HOC x WHERE x.MaPhong = g.MaPhong);

GO

;WITH F AS (
    SELECT v AS Tang FROM (VALUES(3),(4),(5),(6),(7)) X(v)
),
R AS (
    SELECT v AS Phong FROM (VALUES(1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11)) Y(v)
),
Gen AS (
    SELECT 
        MaPhong   = CONCAT('F', Tang, RIGHT('00' + CAST(Phong AS VARCHAR(2)), 2)), -- D101..D111, D201..D211, D301..D311, D401..D411
        LoaiPhong = N'Thực hành',
        SucChua   = CASE 
                        WHEN Phong IN (1,6,7,8,9) THEN 90           -- phòng lớn
                        ELSE 45                                   -- còn lại
                    END,
        ThietBi   = N'PC',
        GhiChu    = NULL
    FROM F CROSS JOIN R
)
INSERT INTO dbo.tb_PHONG_HOC (MaPhong, LoaiPhong, SucChua, ThietBi, GhiChu)
SELECT g.MaPhong, g.LoaiPhong, g.SucChua, g.ThietBi, g.GhiChu
FROM Gen g
WHERE NOT EXISTS (SELECT 1 FROM dbo.tb_PHONG_HOC x WHERE x.MaPhong = g.MaPhong);

GO

SELECT * FROM tb_PHONG_HOC

-----------THEM RANG BUOC MEM--------------
MERGE dbo.tb_RANG_BUOC_MEM AS T
USING (VALUES
  -- RBM-001: Giới hạn ca/ngày cho GV
  ('RBM-001',
   N'Giới hạn số ca/ngày cho giảng viên',
   N'Giới hạn tổng số giờ/ca dạy tối đa trong một ngày cho mỗi giảng viên (ví dụ ≤ 4 ca/ngày) nhằm tránh quá tải.',
   0.90),

  -- RBM-002: Giảm số ngày lên trường của GV
  ('RBM-002',
   N'Giảm số ngày lên trường của giảng viên',
   N'Tối thiểu hóa số ngày phải lên trường (gom ca trong ít ngày hơn) nếu không vi phạm các ràng buộc cứng.',
   0.85),

   ('RBM-003',
   N'Cân bằng tải giảng dạy cho giảng viên',
   N'Mục tiêu là phân bổ số ca dạy đồng đều giữa các giảng viên. Ràng buộc này phạt các lịch trình có độ lệch chuẩn (standard deviation) cao về số ca dạy, tránh tình trạng giảng viên dạy quá nhiều hoặc quá ít.',
   1.0),

   ('RBM-004',
   N'Thưởng khi đáp ứng nguyện vọng giảng viên',
   N'Ưu tiên cao nhất cho việc xếp giảng viên vào đúng khe thời gian (timeslot) họ đã đăng ký. Mỗi lần xếp thành công sẽ được cộng điểm thưởng theo trọng số này. Đây là yếu tố quan trọng nhất để tăng sự hài lòng.',
   1.2),

  -- w_compact: Tối ưu tính liên tục (Gom ca)
  ('RBM-005',
   N'Tối ưu tính liên tục (Gom ca trong ngày)',
   N'Giảm thiểu các khoảng trống trong lịch trình của một giảng viên trong cùng một ngày. Một lịch trình có ca dạy liền kề (ví dụ: Ca 1-2) được đánh giá cao hơn lịch có ca trống xen giữa (ví dụ: Ca 1-4).',
   0.5),

  -- w_unsat: Phạt khi xếp ngoài nguyện vọng
  ('RBM-006',
   N'Phạt khi xếp lịch ngoài nguyện vọng',
   N'Áp dụng điểm phạt khi xếp một giảng viên vào khe thời gian mà họ KHÔNG đăng ký trong danh sách nguyện vọng. Ràng buộc này hoạt động ngược lại với việc thưởng khi đáp ứng nguyện vọng.',
   0.8)
) AS S(MaRangBuoc, TenRangBuoc, MoTa, TrongSo)
ON T.MaRangBuoc = S.MaRangBuoc
WHEN MATCHED THEN
  UPDATE SET T.TenRangBuoc = S.TenRangBuoc,
             T.MoTa        = S.MoTa,
             T.TrongSo     = S.TrongSo
WHEN NOT MATCHED THEN
  INSERT (MaRangBuoc, TenRangBuoc, MoTa, TrongSo)
  VALUES (S.MaRangBuoc, S.TenRangBuoc, S.MoTa, S.TrongSo);


GO

  /* ===== TẠO LỚP CHO DANH SÁCH MÔN ĐÃ CHO (mỗi môn >= 2 nhóm) ===== */
;WITH ListMH AS (
    SELECT * FROM (VALUES
    ('502045'),('502046'),('502047'),('502049'),('502051'),('502052'),('502061'),
    ('502066'),('502068'),('502070'),
    ('50209260'),('503040'),('503044'),('503074'),('503080'),('50308160'),
    ('503109'),('503110'),('503111'),('503112'),
    ('504008'),('504045'),('504048'),('504049'),('504087'),('504088'),
    ('504091'),('50409660'),('50409760'),
    ('505041'),('505043'),('505060'),('50506960'),
    ('502046EN'),('502051EN'),('502061EN'),
    ('502050'),('502071'),('503005'),('503066'),('503107'),('503108'),
    ('503116'),('504074'),('504075'),('504076'),('505010'),('505011')
    ) v(MaMonHoc)
),
M AS ( -- thông tin môn
    SELECT m.MaMonHoc, m.SoTinChi, m.SoTietLT, m.SoTietTH
    FROM dbo.tb_MON_HOC m
    JOIN ListMH l ON l.MaMonHoc = m.MaMonHoc
),
NHOM AS ( -- mỗi môn ít nhất 2 nhóm
    SELECT v AS Nhom_MH FROM (VALUES (1),(2)) X(v)
),
-- Sinh các tổ theo quy tắc: không TH => chỉ tổ 0 ; có TH => tổ 0,1,2
PLAN_CTE AS (
    SELECT 
        m.MaMonHoc,
        n.Nhom_MH,
        togen.To_MH,
        m.SoTinChi, m.SoTietLT, m.SoTietTH
    FROM M m
    CROSS JOIN NHOM n
    CROSS APPLY (
        SELECT To_MH
        FROM (VALUES (0),(1),(2)) v(To_MH)
        WHERE (m.SoTietTH = 0 AND v.To_MH = 0)
           OR (m.SoTietTH > 0 AND v.To_MH IN (0,1,2))
    ) togen
),
-- Tạo chỉ số nhóm (MaMonHoc, Nhom_MH) để gán HeDaoTao/NgonNgu theo NHÓM (không theo tổ)
GROUPS AS (
    SELECT 
        MaMonHoc, Nhom_MH,
        ROW_NUMBER() OVER (ORDER BY MaMonHoc, Nhom_MH) AS rn_grp
    FROM PLAN_CTE
    GROUP BY MaMonHoc, Nhom_MH
),
DECORATED AS (
    SELECT
        g.rn_grp,
        p.MaMonHoc, p.Nhom_MH, p.To_MH,
        -- HeDaoTao theo nhóm (luân phiên 5 loại)
        HeDaoTao = CASE ((g.rn_grp - 1) % 5)
                     WHEN 0 THEN N'Tiêu chuẩn'
                     WHEN 1 THEN N'4+1'
                     WHEN 2 THEN N'Liên kết'
                     WHEN 3 THEN N'CTCLC'
                     WHEN 4 THEN N'ĐHTA'
                   END,
        -- Ngôn ngữ theo nhóm, bám quy tắc hệ đào tạo
        NgonNgu = CASE ((g.rn_grp - 1) % 5)
                    WHEN 2 THEN N'Tiếng Anh'                                        -- Liên kết
                    WHEN 4 THEN N'Tiếng Anh'                                        -- ĐHTA
                    WHEN 3 THEN CASE WHEN g.rn_grp % 2 = 1 THEN N'Tiếng Anh' ELSE N'Tiếng Việt' END -- CTCLC: luân phiên theo nhóm
                    ELSE N'Tiếng Việt'                                              -- Tiêu chuẩn, 4+1
                  END,
        SoLuongSV      = CASE WHEN (p.SoTinChi >= 4 AND p.To_MH = 0 AND p.SoTietTH > 0) THEN 80 ELSE 40 END,
        ThietBiYeuCau  = CASE WHEN p.To_MH > 0 THEN N'PC' ELSE N'TV, Máy chiếu' END,
        SoCaTuan       = CASE WHEN (p.SoTinChi >= 4 AND p.SoTietLT >= 60) THEN 2 ELSE 1 END
    FROM PLAN_CTE p
    JOIN GROUPS g ON g.MaMonHoc = p.MaMonHoc AND g.Nhom_MH = p.Nhom_MH
),
-- Tạo mã lớp theo thứ tự NHÓM rồi TỔ (để dễ nhìn)
ROWNUM AS (
    SELECT 
        ROW_NUMBER() OVER (ORDER BY rn_grp, MaMonHoc, Nhom_MH, To_MH) AS rn,
        *
    FROM DECORATED
),
GEN AS (
    SELECT 
        MaLop = CONCAT('LOP-', FORMAT(rn, '00000000')),
        MaMonHoc, Nhom_MH, To_MH,
        SoLuongSV, HeDaoTao, NgonNgu, ThietBiYeuCau, SoCaTuan
    FROM ROWNUM
)
INSERT INTO dbo.tb_LOP_MONHOC
    (MaLop, MaMonHoc, Nhom_MH, To_MH, SoLuongSV, HeDaoTao, NgonNgu, ThietBiYeuCau, SoCaTuan)
SELECT g.MaLop, g.MaMonHoc, g.Nhom_MH, g.To_MH, g.SoLuongSV, g.HeDaoTao, g.NgonNgu, g.ThietBiYeuCau, g.SoCaTuan
FROM GEN g
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.tb_LOP_MONHOC x
    WHERE x.MaMonHoc = g.MaMonHoc
      AND x.Nhom_MH  = g.Nhom_MH
      AND x.To_MH    = g.To_MH
);

GO

SELECT * FROM tb_LOP_MONHOC


GO

INSERT INTO dbo.tb_DOT_XEP (MaDot, MaDuKienDT, TenDot, TrangThai)
VALUES
('DOT1_2025-2026_HK1', '2025-2026_HK1', N'Đợt xếp lần 1 HK1 2025-2026', 'DRAFT'),
('DOT1_2025-2026_HK2', '2025-2026_HK2', N'Đợt xếp lần 1 HK2 2025-2026', 'DRAFT')


GO


-----------------PHÂN CÔNG GV VÀ LỚP HỌC VÀO ĐỢT---------
DECLARE @MaDot       VARCHAR(20) = 'DOT1_2025-2026_HK1';
DECLARE @TargetPerGV INT = 11;   -- trần cứng 11 lớp/GV trong đợt

/* 0) Đưa tất cả lớp vào đợt @MaDot (nếu chưa có), MaGV = NULL */
INSERT INTO dbo.tb_PHAN_CONG (MaDot, MaLop, MaGV)
SELECT @MaDot, L.MaLop, NULL
FROM dbo.tb_LOP_MONHOC AS L
WHERE NOT EXISTS (
    SELECT 1
    FROM dbo.tb_PHAN_CONG P
    WHERE P.MaDot = @MaDot AND P.MaLop = L.MaLop
);

/* 1) Danh sách lớp CHƯA được gán GV (MaGV IS NULL) trong đợt */
DECLARE @Lop TABLE (
  RowID    INT IDENTITY(1,1) PRIMARY KEY,
  MaLop    VARCHAR(12),
  MaMonHoc VARCHAR(10)
);

INSERT INTO @Lop (MaLop, MaMonHoc)
SELECT P.MaLop, LMH.MaMonHoc
FROM dbo.tb_PHAN_CONG P
JOIN dbo.tb_LOP_MONHOC LMH ON LMH.MaLop = P.MaLop
WHERE P.MaDot = @MaDot AND P.MaGV IS NULL
ORDER BY LMH.MaMonHoc, LMH.Nhom_MH, ISNULL(LMH.To_MH,0), LMH.MaLop;

/* 2) Tải hiện tại TRONG ĐỢT của các GV có thể dạy ÍT NHẤT 1 lớp */
DECLARE @Load TABLE(
  MaGV    VARCHAR(12) PRIMARY KEY,
  LoadCnt INT NOT NULL
);

INSERT INTO @Load(MaGV, LoadCnt)
SELECT GV.MaGV,
       (SELECT COUNT(*) 
        FROM dbo.tb_PHAN_CONG PC 
        WHERE PC.MaDot = @MaDot AND PC.MaGV = GV.MaGV) AS LoadCnt
FROM dbo.tb_GIANG_VIEN GV
WHERE EXISTS (
  SELECT 1
  FROM @Lop LP
  JOIN dbo.tb_GV_DAY_MON GDM
    ON GDM.MaMonHoc = LP.MaMonHoc AND GDM.MaGV = GV.MaGV
);

/* 3) Gán GV cho các lớp còn trống: chỉ chọn GV dưới trần, đủ điều kiện */
DECLARE
  @i INT = 1,
  @n INT = (SELECT COUNT(*) FROM @Lop),
  @MaLop VARCHAR(12),
  @MaMonHoc VARCHAR(10),
  @PickGV VARCHAR(12);

WHILE @i <= @n
BEGIN
  SELECT @MaLop = MaLop, @MaMonHoc = MaMonHoc
  FROM @Lop WHERE RowID = @i;

  -- Chọn GV đủ điều kiện VÀ còn dưới trần trong đợt
  SELECT TOP (1) @PickGV = U.MaGV
  FROM dbo.tb_GV_DAY_MON U
  JOIN @Load LG ON LG.MaGV = U.MaGV
  WHERE U.MaMonHoc = @MaMonHoc
    AND LG.LoadCnt < @TargetPerGV
  ORDER BY LG.LoadCnt ASC, U.MaGV ASC;

  IF @PickGV IS NULL
  BEGIN
    -- Không còn GV nào dưới trần cho lớp này -> để NULL, không gán
    RAISERROR (N'⚠️ Hết GV dưới trần %d lớp cho lớp %s (môn %s). Giữ MaGV = NULL.',
               10, 1, @TargetPerGV, @MaLop, @MaMonHoc);
  END
  ELSE
  BEGIN
    UPDATE dbo.tb_PHAN_CONG
       SET MaGV = @PickGV
     WHERE MaDot = @MaDot AND MaLop = @MaLop;

    UPDATE @Load SET LoadCnt = LoadCnt + 1 WHERE MaGV = @PickGV;
  END

  SET @i = @i + 1;
END

GO

/* 4) Báo cáo nhanh */
-- Phân bổ trong đợt
SELECT GV.MaGV, GV.TenGV, COUNT(PC.MaLop) AS SoLopTrongDot
FROM dbo.tb_GIANG_VIEN GV
LEFT JOIN dbo.tb_PHAN_CONG PC
  ON PC.MaGV = GV.MaGV AND PC.MaDot = 'DOT1_2025-2026_HK1'
GROUP BY GV.MaGV, GV.TenGV
ORDER BY SoLopTrongDot DESC, GV.MaGV;

GO

-- Các lớp còn chưa gán GV
SELECT MaLop
FROM dbo.tb_PHAN_CONG
WHERE MaDot = 'DOT1_2025-2026_HK1' AND MaGV IS NULL
ORDER BY MaLop;


GO


;WITH
Param AS (
    SELECT CAST('DOT1_2025-2026_HK1' AS VARCHAR(20)) AS MaDot
),
-- Mỗi GV nhận số slot ngẫu nhiên trong [2..15]
GV AS (
  SELECT 
      MaGV,
      8 + ABS(CHECKSUM(NEWID())) % 13 AS SlotTarget -- 8-20
  FROM dbo.tb_GIANG_VIEN
),
-- Toàn bộ timeslot KHÔNG Chủ nhật
TS AS (
  SELECT TimeSlotID, Thu, Ca
  FROM dbo.tb_TIME_SLOT
  WHERE Thu <> 8
),
-- Xếp thứ tự ngẫu nhiên các timeslot cho từng GV
Ranked AS (
  SELECT 
      g.MaGV,
      p.MaDot,
      ts.TimeSlotID,
      g.SlotTarget,
      ROW_NUMBER() OVER (
        PARTITION BY g.MaGV
        ORDER BY NEWID()
      ) AS rn
  FROM GV g
  CROSS JOIN TS ts
  CROSS JOIN Param p
),
-- Lấy đúng số lượng slot đã bốc thăm cho mỗi GV
Pick AS (
  SELECT MaGV, MaDot, TimeSlotID
  FROM Ranked
  WHERE rn <= SlotTarget
)
INSERT INTO dbo.tb_NGUYEN_VONG (MaGV, MaDot, TimeSlotID)
SELECT p.MaGV, p.MaDot, p.TimeSlotID
FROM Pick p
WHERE NOT EXISTS (
  SELECT 1
  FROM dbo.tb_NGUYEN_VONG x
  WHERE x.MaGV = p.MaGV AND x.MaDot = p.MaDot AND x.TimeSlotID = p.TimeSlotID
);

GO


SELECT 
    nv.MaGV, gv.TenGV,
    STRING_AGG(ts.TimeSlotID, ', ') WITHIN GROUP (ORDER BY ts.Thu, ts.Ca) AS DanhSachSlot
FROM dbo.tb_NGUYEN_VONG nv
JOIN dbo.tb_GIANG_VIEN gv ON gv.MaGV = nv.MaGV
JOIN dbo.tb_TIME_SLOT ts  ON ts.TimeSlotID = nv.TimeSlotID
WHERE nv.MaDot = 'DOT1_2025-2026_HK1'
GROUP BY nv.MaGV, gv.TenGV
ORDER BY nv.MaGV;


SELECT * FROM tb_LOP_MONHOC
SELECT * FROM tb_PHONG_HOC

SELECT COUNT(*) FROM tb_LOP_MONHOC WHERE ThietBiYeuCau LIKE '%PC%'