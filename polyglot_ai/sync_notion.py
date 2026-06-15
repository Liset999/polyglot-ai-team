import os
import json
import urllib.request
import urllib.error
import sys

# Notion API 基础配置
NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def parse_inline_markdown(text):
    """
    解析行内 Markdown：将 **加粗** 和 `行内代码` 编译为 Notion API 富文本 JSON 结构。
    """
    parts = text.split("**")
    rich_text = []
    
    for idx, part in enumerate(parts):
        if not part:
            continue
        is_bold = (idx % 2 == 1)
        
        # 进一步拆分行内代码
        subparts = part.split("`")
        for sub_idx, subpart in enumerate(subparts):
            if not subpart:
                continue
            is_code = (sub_idx % 2 == 1)
            
            rich_text.append({
                "type": "text",
                "text": {"content": subpart},
                "annotations": {
                    "bold": is_bold,
                    "code": is_code
                }
            })
            
    if not rich_text:
        rich_text = [{"type": "text", "text": {"content": text}}]
    return rich_text

def parse_markdown_to_blocks(content):
    """
    Markdown 文件行编译器，转为 Notion Blocks
    """
    lines = content.split('\n')
    blocks = []
    
    in_code_block = False
    code_content = []
    code_lang = "plain text"
    
    for line in lines:
        stripped = line.strip()
        
        if line.startswith("```"):
            if in_code_block:
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": code_lang
                    }
                })
                in_code_block = False
                code_content = []
            else:
                in_code_block = True
                lang = stripped[3:].strip().lower()
                code_lang = lang if lang in ["python", "javascript", "bash", "json", "shell", "powershell", "yaml", "html", "css"] else "plain text"
            continue
            
        if in_code_block:
            code_content.append(line)
            continue
            
        if not stripped:
            continue
            
        if line.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": parse_inline_markdown(line[2:])}
            })
        elif line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": parse_inline_markdown(line[3:])}
            })
        elif line.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": parse_inline_markdown(line[4:])}
            })
        elif line.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": parse_inline_markdown(line[2:])}
            })
        elif line.startswith("* ") or line.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_inline_markdown(line[2:])}
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": parse_inline_markdown(line)}
            })
            
    return blocks

def sync_to_notion():
    token = os.environ.get("NOTION_TOKEN") or "YOUR_NOTION_INTEGRATION_TOKEN"
    page_id = os.environ.get("NOTION_PAGE_ID") or "YOUR_NOTION_PAGE_ID"
    
    workspace_dir = os.path.dirname(os.path.dirname(__file__))
    note_path = os.path.join(workspace_dir, "skills", "README.md")
    
    if token == "YOUR_NOTION_INTEGRATION_TOKEN" or page_id == "YOUR_NOTION_PAGE_ID":
        print("[ERROR] 请先配置 NOTION_TOKEN 和 NOTION_PAGE_ID！", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(note_path):
        print(f"[ERROR] 找不到本地笔记文件：{note_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    blocks = parse_markdown_to_blocks(content)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    doc_title = "SRE & 自动化引擎学习笔记"

    # --- 1. 读取结构 ---
    print("[Sync] 正在读取 Notion 页面现有结构...")
    list_url = f"{NOTION_API_URL}/blocks/{page_id}/children"
    req = urllib.request.Request(list_url, headers=headers, method="GET")
    
    existing_block_ids = []
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            results = res_data.get("results", [])
            existing_block_ids = [block.get("id") for block in results]
    except urllib.error.HTTPError as e:
        print(f"[ERROR] 读取 Notion 页面失败: HTTP {e.code} - {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
        
    # --- 2. 清空旧 Blocks ---
    if existing_block_ids:
        print(f"[Sync] 正在清空旧数据（共 {len(existing_block_ids)} 个 Block）...")
        for b_id in existing_block_ids:
            del_url = f"{NOTION_API_URL}/blocks/{b_id}"
            req_del = urllib.request.Request(del_url, headers=headers, method="DELETE")
            try:
                with urllib.request.urlopen(req_del, timeout=20) as _:
                    pass
            except Exception as e:
                print(f"[WARNING] 无法删除 block {b_id}: {e}", file=sys.stderr)

    # --- 3. 更新标题 ---
    print("[Sync] 正在更新页面标题...")
    title_url = f"{NOTION_API_URL}/pages/{page_id}"
    title_payload = {
        "properties": {
            "title": [{"text": {"content": doc_title}}]
        }
    }
    req_title = urllib.request.Request(
        title_url,
        data=json.dumps(title_payload).encode("utf-8"),
        headers=headers,
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req_title, timeout=20) as _:
            pass
    except urllib.error.HTTPError as e:
        print(f"[WARNING] 无法更新页面标题: HTTP {e.code} - {e.read().decode('utf-8')}", file=sys.stderr)

    # --- 4. 写入新数据 ---
    print(f"[Sync] 正在写入新数据（共 {len(blocks)} 个 Block）...")
    chunk_size = 80
    for i in range(0, len(blocks), chunk_size):
        chunk = blocks[i:i + chunk_size]
        append_url = f"{NOTION_API_URL}/blocks/{page_id}/children"
        payload = {"children": chunk}
        
        req_append = urllib.request.Request(
            append_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="PATCH"
        )
        
        try:
            with urllib.request.urlopen(req_append, timeout=20) as _:
                pass
        except urllib.error.HTTPError as e:
            print(f"[ERROR] 写入 Block 失败: HTTP {e.code} - {e.read().decode('utf-8')}", file=sys.stderr)
            sys.exit(1)
            
    print("=" * 60)
    print(f"[Sync SUCCESS] 笔记已成功同步至 Notion！")
    print("=" * 60)

if __name__ == "__main__":
    sync_to_notion()
