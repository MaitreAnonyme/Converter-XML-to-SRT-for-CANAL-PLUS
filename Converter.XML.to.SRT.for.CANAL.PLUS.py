import sys
import re
import os
import xml.etree.ElementTree as ET

def clean_time_str(time_str):
    """Convertit le format 00:00:00.000 en 00:00:00,000"""
    if not time_str:
        return "00:00:00,000"
    return time_str.replace('.', ',')

def ms_to_time_str(ms):
    """Reconvertit les millisecondes en format string SRT"""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(int(h), int(m), int(s), int(ms))

def time_to_ms(time_str):
    """Convertit un timestamp en millisecondes"""
    try:
        if ',' in time_str:
            time_str = time_str.replace(',', '.')
        h, m, s = time_str.split(':')
        s, ms = s.split('.')
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
    except (ValueError, AttributeError):
        return 0

def get_color_tag(style_name):
    """Retourne le tag font color selon le style"""
    colors = {
        "textWhite": "#ffffff",
        "textYellow": "#ffff00",
        "textRed": "#ff0000",
        "textGreen": "#00ff00",
        "textCyan": "#00ffff",
        "textMagenta": "#ff00ff"
    }
    code = colors.get(style_name)
    if code:
        return f'<font color="{code}">'
    return ""

def get_align_tag(style_name):
    """Retourne le tag d'alignement ASS/SRT"""
    alignments = {
        "alignStart": "{\\an1}",
        "alignCenter": "{\\an2}",
        "alignEnd": "{\\an3}"
    }
    return alignments.get(style_name, "")

def parse_xml_content(node):
    """Extrait le texte et applique les couleurs récursivement"""
    text_content = ""
    
    if node.text:
        text_content += node.text
    
    for child in node:
        tag = child.tag.split('}')[-1]
        
        if tag == 'br':
            # On remplace les sauts de ligne XML par des espaces pour l'instant
            # (Le nettoyage final gérera la fusion)
            text_content += " " 
        elif tag == 'span':
            span_text = parse_xml_content(child)
            style = child.get('style')
            color_tag = get_color_tag(style)
            
            if color_tag and span_text.strip():
                text_content += f"{color_tag}{span_text}</font>"
            else:
                text_content += span_text
        else:
            text_content += parse_xml_content(child)
            
        if child.tail:
            text_content += child.tail
            
    return text_content

def final_clean(text):
    """Nettoyage final : fusion lignes, nettoyage tags, gestion split couleur"""
    if not text:
        return ""

    # 1. Remplacer les sauts de ligne existants par des espaces (Fusion globale initiale)
    text = text.replace('\n', ' ')
    
    # 2. Normaliser les espaces insécables
    text = text.replace('\xa0', ' ')

    # 3. Réduire les espaces multiples
    text = re.sub(r' +', ' ', text)

    # 4. Remplacements Spécifiques demandés (Tags collés)
    # Ceci va potentiellement coller </font> à <font s'il y avait un espace entre les deux
    text = text.replace("> ", ">")
    text = text.replace(" <", "<")

    # 5. RÈGLE SPÉCIFIQUE : Recréer une entrée (nouvelle ligne) UNIQUEMENT quand les tags se touchent
    # Cela transforme "...</font><font..." en "...</font>\n<font..."
    text = text.replace('</font><font', '</font>\n<font')

    return text.strip()

def process_file(file_path):
    print(f"Traitement de : {file_path}")
    
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        content_str = raw_data.decode('utf-8', errors='ignore')
        ttml_blocks = re.findall(r'(<tt\s+.*?</tt>)', content_str, re.DOTALL)
        
        if not ttml_blocks:
            print("❌ Aucun contenu valide.")
            return

        raw_subs = []

        # --- Parsing ---
        for block in ttml_blocks:
            try:
                root = ET.fromstring(block)
                ns = {'tt': 'http://www.w3.org/ns/ttml'}
                
                paragraphs = root.findall('.//tt:p', ns)
                if not paragraphs:
                    paragraphs = root.findall('.//p')

                for p in paragraphs:
                    begin = p.get('begin')
                    end = p.get('end')
                    p_style = p.get('style')
                    
                    if begin and end:
                        align_tag = get_align_tag(p_style)
                        text = parse_xml_content(p)
                        
                        full_text = f"{align_tag}{text}" if align_tag else text
                        
                        # Nettoyage (Fusion + Split sur changement couleur)
                        clean_txt = final_clean(full_text)
                        
                        if clean_txt:
                            raw_subs.append({
                                'start_ms': time_to_ms(begin),
                                'end_ms': time_to_ms(end),
                                'text': clean_txt
                            })
            except ET.ParseError:
                continue

        # --- Tri ---
        raw_subs.sort(key=lambda x: x['start_ms'])

        # --- Fusion intelligente (Anti-chevauchement) ---
        merged_subs = []
        
        for sub in raw_subs:
            if not merged_subs:
                merged_subs.append(sub)
                continue
            
            last_sub = merged_subs[-1]
            
            is_same_text = (sub['text'] == last_sub['text'])
            is_overlapping = (sub['start_ms'] <= last_sub['end_ms'] + 200)

            if is_same_text and is_overlapping:
                last_sub['end_ms'] = max(last_sub['end_ms'], sub['end_ms'])
            else:
                if sub['start_ms'] < last_sub['end_ms']:
                    last_sub['end_ms'] = sub['start_ms']

                if sub['end_ms'] > sub['start_ms']:
                    merged_subs.append(sub)

        # --- Écriture ---
        dir_name, file_name = os.path.split(file_path)
        base_name = os.path.splitext(file_name)[0]
        output_path = os.path.join(dir_name, base_name + "_FINAL.srt")

        with open(output_path, 'w', encoding='utf-8') as out:
            for idx, sub in enumerate(merged_subs, 1):
                out.write(f"{idx}\n")
                out.write(f"{ms_to_time_str(sub['start_ms'])} --> {ms_to_time_str(sub['end_ms'])}\n")
                out.write(f"{sub['text']}\n\n")

        print(f"✅ Terminé ! Fichier créé : {output_path}")

    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for file_path in sys.argv[1:]:
            process_file(file_path)
        input("\nAppuyez sur Entrée pour quitter...")
    else:
        print("Glissez le fichier .srt sur ce script.")
        input("Appuyez sur Entrée pour quitter...")