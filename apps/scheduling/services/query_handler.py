"""
Xử lý các query và phân tích dữ liệu
"""

import logging
import pandas as pd
from tabulate import tabulate
from typing import List

logger = logging.getLogger(__name__)


class QueryHandler:
    """Xử lý các truy vấn dữ liệu"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_specific_data(self, query: str) -> str:
        """Lấy dữ liệu cụ thể theo query với format đẹp"""
        try:
            df = self.db.execute_query(query)
            if not df.empty:
                try:
                    # Xử lý DataFrame để tránh lỗi với None values
                    clean_df = df.fillna('')  # Thay None bằng chuỗi rỗng
                    for col in clean_df.columns:
                        clean_df[col] = clean_df[col].astype(str)
                    
                    table_str = tabulate(clean_df, headers=clean_df.columns, tablefmt="grid", 
                                       showindex=False, stralign="left")
                    
                    result = f"📊 **Kết quả query ({len(df)} dòng):**\n\n"
                    result += f"```sql\n{query}\n```\n\n"
                    result += f"{table_str}\n\n"
                except Exception as table_error:
                    # Nếu tabulate lỗi, hiển thị theo cách khác
                    result = f"📊 **Kết quả query ({len(df)} dòng):**\n\n"
                    result += f"```sql\n{query}\n```\n\n"
                    for idx, row in df.iterrows():
                        result += f"**Bản ghi {idx+1}:**\n"
                        for col, val in row.items():
                            result += f"  - {col}: {val}\n"
                        result += "\n"
                
                # Thêm thống kê nếu có nhiều dòng
                if len(df) > 5:
                    result += f"📈 **Thống kê:** Tìm thấy {len(df)} bản ghi, {len(df.columns)} cột dữ liệu\n"
                    
                return result
            else:
                return f"❌ **Không có dữ liệu:**\n```sql\n{query}\n```\nKhông tìm thấy bản ghi nào phù hợp."
        except Exception as e:
            return f"❌ **Lỗi thực thi query:**\n```sql\n{query}\n```\nLỗi: {e}"
    
    def get_schedule_conflicts(self, ma_dot: str = None) -> str:
        """Kiểm tra conflict trong lịch học"""
        if ma_dot:
            # Conflict giảng viên - cùng thời gian dạy nhiều lớp
            gv_conflict_query = f"""
            SELECT 
                pc1.MaGV,
                gv.TenGV,
                tkb1.TimeSlotID,
                tkb1.MaLop as Lop1,
                tkb2.MaLop as Lop2,
                tkb1.MaPhong as Phong1,
                tkb2.MaPhong as Phong2
            FROM tb_TKB tkb1
            JOIN tb_TKB tkb2 ON tkb1.TimeSlotID = tkb2.TimeSlotID 
                AND tkb1.MaDot = tkb2.MaDot 
                AND tkb1.MaTKB < tkb2.MaTKB
            JOIN tb_PHAN_CONG pc1 ON tkb1.MaLop = pc1.MaLop AND tkb1.MaDot = pc1.MaDot
            JOIN tb_PHAN_CONG pc2 ON tkb2.MaLop = pc2.MaLop AND tkb2.MaDot = pc2.MaDot
            JOIN tb_GIANG_VIEN gv ON pc1.MaGV = gv.MaGV
            WHERE tkb1.MaDot = '{ma_dot}' AND pc1.MaGV = pc2.MaGV
            """
            
            # Conflict phòng học - cùng phòng cùng thời gian
            room_conflict_query = f"""
            SELECT 
                tkb1.MaPhong,
                ph.LoaiPhong,
                tkb1.TimeSlotID,
                tkb1.MaLop as Lop1,
                tkb2.MaLop as Lop2
            FROM tb_TKB tkb1
            JOIN tb_TKB tkb2 ON tkb1.MaPhong = tkb2.MaPhong 
                AND tkb1.TimeSlotID = tkb2.TimeSlotID 
                AND tkb1.MaDot = tkb2.MaDot 
                AND tkb1.MaTKB < tkb2.MaTKB
            JOIN tb_PHONG_HOC ph ON tkb1.MaPhong = ph.MaPhong
            WHERE tkb1.MaDot = '{ma_dot}'
            """
            
            gv_conflicts = self.db.execute_query(gv_conflict_query)
            room_conflicts = self.db.execute_query(room_conflict_query)
            
            result = "=== KIỂM TRA CONFLICT LỊCH HỌC ===\n\n"
            result += f"📋 Đợt xếp: {ma_dot}\n\n"
            
            if not gv_conflicts.empty:
                result += "⚠️ **CONFLICT GIẢNG VIÊN:**\n"
                table_str = tabulate(gv_conflicts, headers=gv_conflicts.columns, 
                                   tablefmt="grid", showindex=False, stralign="left")
                result += f"{table_str}\n\n"
            else:
                result += "✅ **Không có conflict giảng viên**\n\n"
                
            if not room_conflicts.empty:
                result += "⚠️ **CONFLICT PHÒNG HỌC:**\n"
                table_str = tabulate(room_conflicts, headers=room_conflicts.columns, 
                                   tablefmt="grid", showindex=False, stralign="left")
                result += f"{table_str}\n\n"
            else:
                result += "✅ **Không có conflict phòng học**\n\n"
                
            return result
        
        return "Vui lòng cung cấp mã đợt xếp."
    
    def get_teacher_availability(self, ma_gv: str = None, ma_dot: str = None) -> str:
        """Lấy thông tin lịch trống và nguyện vọng của giảng viên"""
        if not ma_gv or not ma_dot:
            return "Vui lòng cung cấp mã giảng viên và mã đợt xếp."
            
        # Lịch hiện tại của giảng viên
        current_schedule_query = f"""
        SELECT 
            gv.TenGV,
            mh.TenMonHoc,
            lmh.Nhom_MH,
            ts.TimeSlotID,
            ts.Thu,
            ts.Ca,
            ktg.TenCa,
            ktg.GioBatDau,
            ktg.GioKetThuc,
            tkb.MaPhong
        FROM tb_PHAN_CONG pc
        JOIN tb_GIANG_VIEN gv ON pc.MaGV = gv.MaGV
        JOIN tb_LOP_MONHOC lmh ON pc.MaLop = lmh.MaLop
        JOIN tb_MON_HOC mh ON lmh.MaMonHoc = mh.MaMonHoc
        LEFT JOIN tb_TKB tkb ON pc.MaLop = tkb.MaLop AND pc.MaDot = tkb.MaDot
        LEFT JOIN tb_TIME_SLOT ts ON tkb.TimeSlotID = ts.TimeSlotID
        LEFT JOIN tb_KHUNG_TG ktg ON ts.Ca = ktg.MaKhungGio
        WHERE pc.MaGV = '{ma_gv}' AND pc.MaDot = '{ma_dot}'
        ORDER BY ts.Thu, ts.Ca
        """
        
        # Nguyện vọng của giảng viên
        preferences_query = f"""
        SELECT 
            nv.TimeSlotID,
            ts.Thu,
            ts.Ca,
            ktg.TenCa,
            ktg.GioBatDau,
            ktg.GioKetThuc
        FROM tb_NGUYEN_VONG nv
        JOIN tb_TIME_SLOT ts ON nv.TimeSlotID = ts.TimeSlotID
        JOIN tb_KHUNG_TG ktg ON ts.Ca = ktg.MaKhungGio
        WHERE nv.MaGV = '{ma_gv}' AND nv.MaDot = '{ma_dot}'
        ORDER BY ts.Thu, ts.Ca
        """
        
        current_schedule = self.db.execute_query(current_schedule_query)
        preferences = self.db.execute_query(preferences_query)
        
        result = f"=== LỊCH GIẢNG VIÊN {ma_gv} ===\n\n"
        
        if not current_schedule.empty:
            result += "📅 LỊCH HIỆN TẠI:\n"
            result += current_schedule.to_string(index=False) + "\n\n"
        else:
            result += "📅 Chưa có lịch được xếp\n\n"
            
        if not preferences.empty:
            result += "💡 NGUYỆN VỌNG THỜI GIAN:\n"
            result += preferences.to_string(index=False) + "\n\n"
        else:
            result += "💡 Chưa đăng ký nguyện vọng\n\n"
            
        return result
    
    def get_room_utilization(self, ma_dot: str = None) -> str:
        """Phân tích tỷ lệ sử dụng phòng học"""
        if not ma_dot:
            return "Vui lòng cung cấp mã đợt xếp lịch."
            
        room_usage_query = f"""
        SELECT 
            ph.MaPhong,
            ph.LoaiPhong,
            ph.SucChua,
            COUNT(tkb.MaTKB) as SoTietSuDung,
            CAST(COUNT(tkb.MaTKB) * 100.0 / 35 AS DECIMAL(5,2)) as TyLeSuDung
        FROM tb_PHONG_HOC ph
        LEFT JOIN tb_TKB tkb ON ph.MaPhong = tkb.MaPhong AND tkb.MaDot = '{ma_dot}'
        GROUP BY ph.MaPhong, ph.LoaiPhong, ph.SucChua
        ORDER BY TyLeSuDung DESC
        """
        
        room_usage = self.db.execute_query(room_usage_query)
        
        result = f"=== TỶ LỆ SỬ DỤNG PHÒNG HỌC (Đợt: {ma_dot}) ===\n\n"
        
        if not room_usage.empty:
            result += "📊 CHI TIẾT SỬ DỤNG:\n"
            result += room_usage.to_string(index=False) + "\n\n"
            
            # Phân tích tổng quan
            avg_usage = room_usage['TyLeSuDung'].mean()
            overused = room_usage[room_usage['TyLeSuDung'] > 80]
            underused = room_usage[room_usage['TyLeSuDung'] < 20]
            
            result += f"📈 Tỷ lệ sử dụng trung bình: {avg_usage:.2f}%\n"
            result += f"⚠️ Phòng sử dụng cao (>80%): {len(overused)}\n"
            result += f"💡 Phòng sử dụng thấp (<20%): {len(underused)}\n"
            
        return result
