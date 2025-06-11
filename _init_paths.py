# # _init_paths.py
# import sys
# import os
# from pathlib import Path
#
#
# def init():
#     # 获取项目根目录（兼容直接运行和打包后运行）
#     project_root = Path(__file__).parent
#
#     # 确保项目根目录在Python路径中
#     if str(project_root) not in sys.path:
#         sys.path.insert(0, str(project_root))
#
#     # 设置conda环境变量（关键！）
#     os.environ['CONDA_PREFIX'] = r'D:\Anaconda3\envs\gr_py310'
#     os.environ['CONDA_DEFAULT_ENV'] = 'gr_py310'
#     os.environ['PYTHONPATH'] = str(project_root)
#
#
# init()
