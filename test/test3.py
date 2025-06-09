
import os
from datetime import datetime


def create_date_folders(start_date, end_date, base_path="."):
    """
    根据日期范围创建文件夹

    参数:
        start_date (str): 开始日期，格式为"YYYY-MM-DD"
        end_date (str): 结束日期，格式为"YYYY-MM-DD"
        base_path (str): 基础路径，默认为当前目录
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        if start > end:
            print("错误：开始日期不能晚于结束日期")
            return

        current = start
        while current <= end:
            folder_name = current.strftime("%Y-%m-%d")
            folder_path = os.path.join(base_path, folder_name)

            try:
                os.makedirs(folder_path, exist_ok=True)
                print(f"已创建文件夹: {folder_path}")
            except Exception as e:
                print(f"创建文件夹 {folder_path} 失败: {e}")

            current = current.replace(day=current.day + 1)

    except ValueError as e:
        print(f"日期格式错误，请使用'YYYY-MM-DD'格式: {e}")


if __name__ == "__main__":
    print("批量创建日期文件夹工具")
    print("文件夹名称格式为: YYYY-MM-DD")
    print("=" * 40)

    # start_date = input("请输入开始日期(YYYY-MM-DD): ")
    # end_date = input("请输入结束日期(YYYY-MM-DD): ")
    # base_path = input("请输入保存路径(留空则为当前目录): ").strip()
    #
    # if not base_path:
    #     base_path = "."
    #
    # create_date_folders(start_date, end_date, base_path)

    create_date_folders("2025-06-01", "2025-06-05", "../media")
    print("文件夹创建完成！")
