#!/usr/bin/env python3
"""Kiểm tra xem có GV nào dạy cả LT và TH không."""

import sys
sys.path.insert(0, '.')

from validator import Faculty

def main():
    faculty = Faculty('dot1.ctt')
    
    # Group courses by teacher
    teacher_courses = {}
    for i, course in enumerate(faculty.course_vect):
        teacher = course.teacher
        course_type = course.course_type
        if teacher not in teacher_courses:
            teacher_courses[teacher] = []
        teacher_courses[teacher].append((f"C{i}", course_type))
    
    # Find teachers teaching both LT and TH
    mixed_teachers = {}
    for teacher, courses in teacher_courses.items():
        types = set(ct for _, ct in courses)
        if len(types) > 1:
            mixed_teachers[teacher] = courses
    
    print(f"✅ Total teachers: {len(teacher_courses)}")
    print(f"⚠️  Teachers teaching BOTH LT and TH: {len(mixed_teachers)}")
    print()
    
    if mixed_teachers:
        print("Teachers with mixed types:")
        for teacher, courses in list(mixed_teachers.items())[:5]:
            lt_count = sum(1 for _, ct in courses if ct == 'LT')
            th_count = sum(1 for _, ct in courses if ct == 'TH')
            print(f"  {teacher}: {lt_count} LT courses, {th_count} TH courses")
            for course_id, course_type in courses[:3]:
                print(f"    - {course_id} ({course_type})")
    else:
        print("✅ No teacher teaches both LT and TH - consolidation logic is safe!")

if __name__ == '__main__':
    main()
