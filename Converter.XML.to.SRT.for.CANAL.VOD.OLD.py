import sys
import re
import os

def ms_to_srt_time(ms):
    """Convertit des millisecondes en format temps SRT (HH:MM:SS,mmm)"""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def parse_time(t_str):
    """Convertit un timestamp HH:MM:SS.mmm en millisecondes"""
    parts = t_str.replace(',', '.').split(':')
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split('.')
        s = int(s_parts[0])
        ms = int(s_parts[1]) if len(s_parts) > 1 else 0
        return h * 3600000 + m * 60000 + s * 1000 + ms
    return 0

def process_file(filepath):
    # Vérifier l'extension
    if not filepath.lower().endswith(('.mp4', '.xml')):
        print(f"Ignoré (ne se termine pas par .mp4 ou .xml) : {os.path.basename(filepath)}")
        return

    try:
        # Lecture en ignorant les erreurs d'encodage (pratique avec les MP4 binaires)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Erreur de lecture du fichier {os.path.basename(filepath)}: {e}")
        return

    # Séparer le fichier en segments (à chaque "<?xml") 
    # Indispensable car les VOD ont souvent des en-têtes XML répétés à chaque fragment.
    segments = re.split(r'<\?xml', content, flags=re.IGNORECASE)
    
    subs = []
    
    # Expressions régulières pour cibler les balises
    style_color_re = re.compile(r"<style\s+xml:id=['\"]([^'\"]+)['\"][^>]*tts:color=['\"]#([0-9a-fA-F]{6})[0-9a-fA-F]{2}['\"]", re.IGNORECASE)
    style_align_re = re.compile(r"<style\s+xml:id=['\"]([^'\"]+)['\"][^>]*tts:textAlign=['\"](start|left|center|end|right)['\"]", re.IGNORECASE)
    
    # NOUVEAU : Regex pour cibler spécifiquement les balises <p ... /> vides
    empty_p_tag_re = re.compile(r"<p\s+[^>]*/>", re.IGNORECASE)
    
    p_tag_re = re.compile(r"<p\s+[^>]*begin=['\"]([\d:\.]+)['\"]\s+end=['\"]([\d:\.]+)['\"][^>]*style=['\"]([^'\"]+)['\"][^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)
    span_tag_re = re.compile(r"<span\s+[^>]*style=['\"]([^'\"]+)['\"][^>]*'preserve'>(.*?)</span>", re.IGNORECASE | re.DOTALL)
    br_tag_re = re.compile(r"<br\s*/?>", re.IGNORECASE)

    align_map = {
        "start": "{\\an1}",
        "left": "{\\an1}",
        "center": "{\\an2}",
        "end": "{\\an3}",
        "right": "{\\an3}"
    }

    current_colors = {}
    current_aligns = {}

    for segment in segments:
        if not segment.strip():
            continue
            
        # --- NOUVEAU : Nettoyer le segment en supprimant les balises <p ... /> vides pour éviter le décalage
        segment = empty_p_tag_re.sub("", segment)
            
        # 1. Mise à jour des styles depuis l'en-tête (écrase les précédents si même ID)
        for match in style_color_re.finditer(segment):
            style_id = match.group(1)
            # Isoler les 6 premiers hexadécimaux et les formater en couleur (ex: #ffffff)
            color_hex = f"#{match.group(2).lower()}"
            current_colors[style_id] = color_hex
            
        for match in style_align_re.finditer(segment):
            style_id = match.group(1)
            align_txt = match.group(2).lower()
            if align_txt in align_map:
                current_aligns[style_id] = align_map[align_txt]
                
        # 2. Extraction des balises <p>
        for p_match in p_tag_re.finditer(segment):
            begin_ms = parse_time(p_match.group(1))
            end_ms = parse_time(p_match.group(2))
            p_style = p_match.group(3)
            inner_html = p_match.group(4)
            
            an_tag = current_aligns.get(p_style, "{\\an2}") # Centre par défaut si introuvable
            
            # Diviser par balises <br /> pour respecter les sauts de lignes
            parts = br_tag_re.split(inner_html)
            
            final_lines = []
            for part in parts:
                line_spans = []
                for span_match in span_tag_re.finditer(part):
                    span_style = span_match.group(1)
                    text = span_match.group(2)
                    
                    # Supprimer les espaces collés aux balises </span> et preserve
                    text = text.strip()
                    
                    if not text:
                        continue
                        
                    # Reconvertir les symboles HTML (apostrophes, etc.)
                    text = text.replace("&apos;", "'").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    
                    # Appliquer la couleur et la mettre en forme HTML SRT
                    color_hex = current_colors.get(span_style, "#ffffff")
                    line_spans.append(f'<font color="{color_hex}">{text}</font>')
                
                if line_spans:
                    final_lines.append(" ".join(line_spans))
            
            if final_lines:
                subs.append({
                    "start": begin_ms,
                    "end": end_ms,
                    "text": an_tag + "\n".join(final_lines)
                })

    if not subs:
        print(f"Aucun sous-titre n'a été trouvé dans {os.path.basename(filepath)}")
        return

    # Tri global chronologique
    subs.sort(key=lambda x: x["start"])

    # Fusion des doublons consécutifs (très fréquent sur les pistes DASH et les fichiers fragmentés)
    merged_subs = []
    for sub in subs:
        if not merged_subs:
            merged_subs.append(sub)
        else:
            last_sub = merged_subs[-1]
            
            is_same_text = (sub['text'] == last_sub['text'])
            is_overlapping = (sub['start'] <= last_sub['end'] + 200)

            if is_same_text and is_overlapping:
                # Extension du temps de fin plutôt que recréation de ligne
                last_sub['end'] = max(last_sub['end'], sub['end'])
            else:
                # Couper le sous-titre précédent s'ils se marchent dessus
                if sub['start'] < last_sub['end']:
                    last_sub['end'] = sub['start']

                if sub['end'] > sub['start']:
                    merged_subs.append(sub)

    # Écriture du fichier final
    dir_name, file_name = os.path.split(filepath)
    base_name = os.path.splitext(file_name)[0]
    out_filepath = os.path.join(dir_name, base_name + "_FINAL.srt")
    
    with open(out_filepath, 'w', encoding='utf-8') as out:
        for idx, sub in enumerate(merged_subs, 1):
            out.write(f"{idx}\n")
            out.write(f"{ms_to_srt_time(sub['start'])} --> {ms_to_srt_time(sub['end'])}\n")
            out.write(f"{sub['text']}\n\n")

    print(f"✅ Conversion terminée : {os.path.basename(out_filepath)}")

if __name__ == '__main__':
    # sys.argv[1:] récupère tous les fichiers glissés et déposés dessus
    if len(sys.argv) < 2:
        print("Veuillez glisser et déposer au moins un fichier .mp4 ou .xml sur ce script.")
        input("Appuyez sur Entrée pour quitter...")
        sys.exit(1)

    print("Traitement en cours...\n")
    for path in sys.argv[1:]:
        process_file(path)
        
    print("\nTous les fichiers ont été traités !")
    input("Appuyez sur Entrée pour fermer cette fenêtre...")