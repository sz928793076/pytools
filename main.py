import os


def merge_sql_inserts_in_batches(input_file_path, batch_size=100):
    """
    从指定路径的文件读取单条 INSERT 语句，按指定数量分组合并为批量 INSERT，并生成输出文件。

    :param input_file_path: 包含单条 INSERT 语句的源文件的完整路径。
    :param batch_size: 每个批次包含的 INSERT 语句数量，默认为 100。
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_file_path):
        print(f"错误: 找不到输入文件 {input_file_path}")
        return

    # 确定输出文件路径 (在同目录下生成)
    base_name = os.path.splitext(input_file_path)[0]  # 获取不带扩展名的文件名
    output_file_path = f"{base_name}_batched.sql"

    single_statements = []
    try:
        # 1. 读取文件内容
        with open(input_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 按分号分割语句，并清理空白和空行
            statements = [stmt.strip() for stmt in content.split(';') if stmt.strip()]

            # 过滤出 INSERT 语句 (增加健壮性)
            single_statements = [stmt for stmt in statements if stmt.upper().lstrip().startswith("INSERT")]

        if not single_statements:
            print(f"警告: 在文件 {input_file_path} 中未找到有效的 INSERT 语句。")
            with open(output_file_path, 'w', encoding='utf-8') as f_out:
                f_out.write("-- No valid INSERT statements found to merge.\n")
            return

        total_statements = len(single_statements)
        print(f"总共找到 {total_statements} 条有效的 INSERT 语句。")

        merged_statements = []
        # 2. 按 batch_size 分组处理
        for i in range(0, total_statements, batch_size):
            batch = single_statements[i:i + batch_size]
            # print(f"处理批次 {i//batch_size + 1}, 包含 {len(batch)} 条语句...") # 可选：打印进度

            # 3. 解析当前批次第一条语句以获取表名和列名
            first_stmt = batch[0]
            parts = first_stmt.split('VALUES', 1)
            if len(parts) != 2:
                print(f"警告: 无法解析批次 {i // batch_size + 1} 的第一条语句，跳过该批次。语句: {first_stmt}")
                continue

            insert_part = parts[0].strip()
            # 收集当前批次所有语句的 VALUES 部分
            all_values_for_batch = []
            for stmt in batch:
                # 为了健壮性，再次检查 VALUES
                parts = stmt.split('VALUES', 1)
                if len(parts) != 2:
                    print(f"警告: 无法解析批次 {i // batch_size + 1} 中的语句，跳过。语句: {stmt}")
                    continue
                values_part = parts[1].strip()
                if values_part.startswith('(') and values_part.endswith(')'):
                    values_part = values_part[1:-1]
                all_values_for_batch.append(values_part)

            # 4. 拼接当前批次的批量 INSERT 语句
            if all_values_for_batch:  # 确保有有效值才生成语句
                merged_statement = f"{insert_part} VALUES\n" + ",\n".join(
                    [f"({v})" for v in all_values_for_batch]) + ";\n"
                merged_statements.append(merged_statement)

        if not merged_statements:
            print("错误: 没有成功生成任何批量 INSERT 语句。")
            with open(output_file_path, 'w', encoding='utf-8') as f_out:
                f_out.write("-- Error: No batched INSERT statements were generated.\n")
            return

        # 5. 将所有合并后的语句写入到输出文件
        with open(output_file_path, 'w', encoding='utf-8') as f_out:
            # 可以在文件开头添加注释说明
            f_out.write(f"-- 合并后的批量 INSERT 语句\n")
            f_out.write(f"-- 原文件: {input_file_path}\n")
            f_out.write(f"-- 批次大小: {batch_size}\n")
            f_out.write(f"-- 总共生成批次: {len(merged_statements)}\n")
            f_out.write("-- -----------------------------------------\n\n")

            for i, merged_stmt in enumerate(merged_statements):
                f_out.write(f"-- 批次 {i + 1}\n")
                f_out.write(merged_stmt)
                f_out.write("\n")  # 批次之间添加空行

        print(f"成功: 已将 {total_statements} 条 INSERT 语句按每批 {batch_size} 条合并，并保存到 {output_file_path}")

    except Exception as e:
        error_msg = f"处理过程中发生错误: {e}"
        print(error_msg)
        # 将错误信息也写入输出文件
        with open(output_file_path, 'w', encoding='utf-8') as f_out:
            f_out.write(f"-- Error during merge: {e}\n")


# --- 使用指定的文件路径 ---
# 请确保路径字符串前的 'r' 存在，以避免转义字符问题
input_sql_file_path = r"C:\Users\sunyangzhe\Documents\WXWork\1688858362312154\Cache\File\2025-09\qwzb-20250921\qwzb-20250921.sql"

if __name__ == '__main__':
    merge_sql_inserts_in_batches(input_sql_file_path, batch_size=100)




