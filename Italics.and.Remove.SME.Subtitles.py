import sys
import os
import re

def process_srt_file(file_path):
    # 1. Lire le contenu du fichier
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        
    # Normalisation des sauts de ligne
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = content.split('\n\n')
    
    parsed_blocks = []
    for block in blocks:
        if not block.strip():
            continue
        lines = block.split('\n')
        if len(lines) >= 3:
            parsed_blocks.append({
                'index': lines[0],
                'timestamp': lines[1],
                'text': lines[2:]
            })
            
    # ==========================================
    # PREMIER EXPORT : SME + Italique
    # ==========================================
    blocks_sme = []
    for block in parsed_blocks:
        new_text = []
        text_lines = list(block['text'])
        
        for i in range(len(text_lines)):
            line = text_lines[i]
            
            # Ignorer le processus si c'est un tag de couleur qui contient uniquement "..." ou "---"
            if re.search(r'<font color="#[0-9a-fA-F]{6}">(\.\.\.|---)</font>', line, flags=re.IGNORECASE):
                new_text.append(line)
                continue
                
            line_lower = line.lower()
            is_red = '<font color="#ff0000">' in line_lower
            is_green = '<font color="#00ff00">' in line_lower
            is_cyan = '<font color="#00ffff">' in line_lower
            is_magenta = '<font color="#ff00ff">' in line_lower
            is_yellow = '<font color="#ffff00">' in line_lower
            
            # Ajout des italiques pour Rouge, Vert, Bleu cyan, Rose magenta
            if is_red or is_green or is_cyan or is_magenta:
                line = re.sub(r'(<font color="#[0-9a-fA-F]{6}">.*?</font>)', r'<i>\1</i>', line, flags=re.IGNORECASE)
            
            # Gestion spéciale pour le Jaune (Radio)
            elif is_yellow:
                has_star = re.search(r'<font color="#ffff00">(-?)\*(-?)(.*?)</font>', line, flags=re.IGNORECASE)
                if has_star:
                    # Italique sur la ligne actuelle
                    line = re.sub(r'(<font color="#ffff00">.*?</font>)', r'<i>\1</i>', line, flags=re.IGNORECASE)
                    
                    # Vérifier si l'italique doit continuer sur la deuxième ligne
                    if i + 1 < len(text_lines):
                        next_line = text_lines[i+1]
                        is_next_yellow = '<font color="#ffff00">' in next_line.lower()
                        
                        # Extraire le texte après les tags pour vérifier s'il n'y a PAS de tiret "-"
                        m_next = re.match(r'^((?:<[^>]+>)*)(.*)$', next_line)
                        next_text = m_next.group(2) if m_next else next_line
                        
                        if is_next_yellow and not next_text.startswith('-'):
                            text_lines[i+1] = re.sub(r'(<font color="#ffff00">.*?</font>)', r'<i>\1</i>', next_line, flags=re.IGNORECASE)
                            
            new_text.append(line)
            
        blocks_sme.append({
            'index': block['index'],
            'timestamp': block['timestamp'],
            'text': new_text
        })
        
    base_name = os.path.splitext(file_path)[0]
    out1_path = base_name + "_SME+Italique_Final.srt"
    
    with open(out1_path, 'w', encoding='utf-8') as f:
        for i, b in enumerate(blocks_sme):
            f.write(f"{i+1}\n{b['timestamp']}\n" + '\n'.join(b['text']) + '\n\n')

    # ==========================================
    # DEUXIÈME EXPORT : Full + Italique
    # ==========================================
    blocks_full = []
    for block in blocks_sme:
        new_text = []
        for line in block['text']:
            # 1. Supprimer les balises de placement
            line = re.sub(r'\{\\an[123]\}', '', line)
            
            # 2, 3, 4. Supprimer les lignes (rouge, vert, magenta)
            if re.search(r'<font color="#ff0000">', line, flags=re.IGNORECASE): continue
            if re.search(r'<font color="#00ff00">', line, flags=re.IGNORECASE): continue
            if re.search(r'<font color="#ff00ff">', line, flags=re.IGNORECASE): continue
            
            # 5, 6, 7. Supprimer les lignes de silence (blanc, jaune, cyan) avec "..." ou "---"
            text_only = re.sub(r'<[^>]+>', '', line).strip()
            if text_only in ['...', '---']:
                if re.search(r'<font color="#(ffffff|ffff00|00ffff)">', line, flags=re.IGNORECASE):
                    continue
                    
            # 9. Supprimer les caractères spéciaux
            line = line.replace('(', '').replace(')', '').replace('*', '')
            
            new_text.append(line)
            
        # Si le sous-titre est vide suite aux suppressions, on l'ignore
        if not new_text:
            continue
            
        lines_info = []
        for line in new_text:
            m = re.match(r'^((?:<[^>]+>)*)(.*)$', line)
            if m:
                tags = m.group(1)
                txt = m.group(2)
            else:
                tags = ""
                txt = line
                
            # 10. Ajoute un espace après le "-" s'il est collé au texte
            txt = re.sub(r'^-([^\s])', r'- \1', txt)
            
            has_dash = txt.startswith('- ')
            lines_info.append({"tags": tags, "text": txt, "has_dash": has_dash})
            
        # 11. Ajout automatique d'un tiret à la ligne 1 si seule la ligne 2 en possède un
        if len(lines_info) == 2:
            if not lines_info[0]["has_dash"] and lines_info[1]["has_dash"]:
                lines_info[0]["text"] = "- " + lines_info[0]["text"]
                lines_info[0]["has_dash"] = True
                
        # Compter le nombre de tirets au début des lignes de ce sous-titre
        total_dashes = sum(1 for info in lines_info if info["has_dash"])
        
        for info in lines_info:
            # 12a. Supprimer tous les tags de couleurs restants
            info["tags"] = re.sub(r'</?font[^>]*>', '', info["tags"], flags=re.IGNORECASE)
            info["text"] = re.sub(r'</?font[^>]*>', '', info["text"], flags=re.IGNORECASE)
            
            # 12b. Supprimer le tiret "seul" (s'il n'y a qu'un tiret dans tout le bloc)
            if total_dashes == 1 and info["has_dash"]:
                info["text"] = info["text"][2:] # Supprime le "- "
                
        # 8. Reconstruire les lignes finales (conservation des balises <i> intactes)
        final_text = [info["tags"] + info["text"] for info in lines_info]
        
        blocks_full.append({
            'timestamp': block['timestamp'],
            'text': final_text
        })
        
    out2_path = base_name + "_Full+Italique_Final.srt"
    
    with open(out2_path, 'w', encoding='utf-8') as f:
        # Ré-indexation automatique des sous-titres Full (1, 2, 3...)
        for i, b in enumerate(blocks_full):
            f.write(f"{i+1}\n{b['timestamp']}\n" + '\n'.join(b['text']) + '\n\n')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Glissez-déposez un ou plusieurs fichiers .srt sur ce script pour lancer le traitement.")
        input("Appuyez sur Entrée pour quitter...")
    else:
        for arg in sys.argv[1:]:
            if os.path.isfile(arg) and arg.lower().endswith('.srt'):
                print(f"Traitement en cours : {os.path.basename(arg)}")
                process_srt_file(arg)
        print("Terminé ! Les fichiers exportés ont été créés.")
        input("Appuyez sur Entrée pour quitter...")