import json
import sys
import os

def update_json_node(file_path, node_id, param_name, new_value):
    try:
        if not os.path.exists(file_path):
            print(f"Ошибка: Файл {file_path} не найден.")
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            # API Format
            if node_id in data:
                node = data[node_id]
                inputs = node.get("inputs", {})
                inputs[param_name] = new_value
                node["inputs"] = inputs
                data[node_id] = node
                print(f"Успешно (API формат): Нода {node_id}, параметр '{param_name}' = '{new_value}'")
            # UI Editor Format
            elif "nodes" in data:
                updated = False
                for dict_node in data["nodes"]:
                    if str(dict_node.get("id")) == str(node_id):
                        if "properties" in dict_node:
                            dict_node["properties"][param_name] = new_value
                        if "inputs" in dict_node and isinstance(dict_node["inputs"], dict):
                             dict_node["inputs"][param_name] = new_value
                             updated = True
                        else:
                             # Initialize inputs parameter
                             dict_node["inputs"] = {param_name: new_value}
                             updated = True
                if updated:
                    print(f"Успешно (UI формат): Нода {node_id}, параметр '{param_name}' = '{new_value}'")
                else:
                    print(f"Ошибка: Нода с ID {node_id} не найдена или не обновлена.")
                    return
            else:
                 print(f"Ошибка: Нода {node_id} не найдена в файле.")
                 return
        else:
            print("Ошибка: Неверный или неизвестный формат JSON.")
            return

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    except Exception as e:
        print(f"Произошла ошибка при обновлении: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Использование: python update_json.py <путь_к_json> <id_ноды> <имя_параметра> <новое_значение>")
        sys.exit(1)
        
    js_path = sys.argv[1]
    n_id = sys.argv[2]
    p_name = sys.argv[3]
    val = " ".join(sys.argv[4:])
    
    # Primitive typing logic
    try:
        if val.isdigit(): 
            val = int(val)
        elif val.replace('.', '', 1).isdigit(): 
            val = float(val)
        elif val.lower() == 'true': 
            val = True
        elif val.lower() == 'false': 
            val = False
    except:
        pass

    update_json_node(js_path, n_id, p_name, val)
