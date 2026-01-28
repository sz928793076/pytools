import os
from PIL import Image


def jpg_to_png(source_folder, output_folder):
    # 如果输出目录不存在，创建它
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(source_folder):
        if filename.lower().endswith(('.jpg', '.jpeg')):
            # 1. 构建路径
            img_path = os.path.join(source_folder, filename)

            # 2. 打开图片
            with Image.open(img_path) as img:
                # 3. 构建新的文件名 (把 .jpg 换成 .png)
                new_filename = os.path.splitext(filename)[0] + ".png"
                new_path = os.path.join(output_folder, new_filename)

                # 4. 保存为 PNG
                img.save(new_path, "PNG")
                print(f"已转换: {filename} -> {new_filename}")


if __name__ == "__main__":
    # 配置你的文件夹路径
    # 假设你的JPG都在 'raw_screenshots' 文件夹，想存到 'assets'
    jpg_to_png('./raw_screenshots', './assets')