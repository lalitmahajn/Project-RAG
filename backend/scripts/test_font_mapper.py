import sys
import re
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


array_one = [
    # PMPML ADDITIONS
    "è", "Am¡Y", "H§y Ora", "©©", "« m", "H r", "« r", "mm", "H _obm", "§ Q", "Šg©", "Jìh©_|Q>", "o«", "H Q", "} Q", "{H$bmoñH$a", "H d", "§ n", "gmdaH$a^dZ", "Ì ~", "w §", "¥ î", "S Z", "Ao", "R m", "o Ý", "åw`", "lrm", "½`w©",  
    # PMPML ADDITIONS DONE
    ">", "$","[", "p","“","”",                  
    "µH","™","˜","µJ","µO","µS","µT","µ\\",                                
    "ª", "£", "¤", "u", "v",      "}", "]",						 			
    "›","@","&","\"","'",                        		                  
    "ú","j","k","l","Ì","Í","Î",                        		            
    "®","¯","é","ê",                        		                        
    
    "#","‚","ƒ","„","†", "‡","ˆ","‰",                        		      
    "’","“","”","•","¬","–","—","œ",                        		      
    "³", "¶",  "¸",  "¹","º","¼", "Ã", "¾","Å","Æ","Ç","È","É",             
    "Ð","Ñ","Ò","Ó","Ô","Õ","Ö","×","Ø","Ù","Ú","Û","Þ","à","á","ï","ð",    
    "ò","ó",   "õ","ö","÷","ø",    "ü","ý",                           		
    "ç", "Œ", "´",  "«",                       		                  		
    
    "Š","»","½", "¿","H","I","J","K","L",                                   
    "À","Á","Â","Ä","M","N","O","P",                                        
    "Q","R","S","T","Ê","U",                        		            	
    "Ë", "Ï", "Ü","Ý","V","W","X","Y","Z",                       	      	
    "ß","â","ã","ä","å","n","\\","~", "^","_",                        		
    
    "æ", "ë","ì","í","î", "ù",  "û", "ñ","ô",                               
    "`","a","b","c","d","e","f","g","h","i",                        		
    
    "Am¡","Amo","Am°","Am","A","B©","B","C","D","F","G","Eo","E",           
    
    "m", "r","s", "t","ww","w","x","y","z","¥","¦","|","o","¡","¢","…","§§","§","¨","µ", 
    "þ","ÿ","°","±","²",                                                       		
    
    "्ा","्ो","्ौ","अो","अा","आै","आे","ाो","ाॅ","ॅा","ाे",
    "ंु","ेे","अै","ाे","अे","ंा","अॅ","ाै","ैा","ंृ",
    "ँा","ँू","ेा","ंे","ाें","ॅं","ंॅ"," ः","ंू"
]

array_two = [
    # PMPML ADDITIONS
    "ऱ्", "औंध", "कूंजीर", "©", "«m", "Hr", "«r", "आ", "कमेला", "§Q", "र्क्स", "गवर्नमेंट", "«o", "HQ", "}Q", "किर्लोस्कर", "Hd", "§n","gmdaH$a ^dZ", "Ì~", "w§", "¥î", "SZ", "ए", "Rm", "oÝ", "å`w", "lr", "र्ग्यु", 
    # PMPML ADDITIONS DONE
    
    "","","{","{","\"","'",  		
    "क़","ख़्","ख़","ग़","ज़","ड़","ढ़","फ़", 
    "ं©",  "ै©","ैं©","ी©","ीं©", "े©", "ें©",             		
    "ॐ","ऽ","।","‘","’",                                			
    "क्ष्","क्ष","ज्ञ","श्र","त्र","त्र्","त्त्",                                 	
    "्रु","्रू","रु","रू",   	                                      	
                                                          
    "ञ्च्","ज्ज्","च्च","ल्ल","ह्ण","ह्ल","ह्व","्व",                               
    "ङ्क","ङ्ख","ङ्ग","ङ्घ","ङ्क्ष","ह्न","ड्ढ","श्व",                             	
    "्न", "ङ्म", "क्क","क्व","क्त","ख्र", "झ्र",  "ग्न", "ट्ट","ट्ठ","ठ्ठ","ड्ड","ड्ढ",     		
    "द्र","दृ","द्ग","द्घ","द्द","द्ध","द्न","द्ब","द्भ","द्म","द्य","द्व","न्न","प्र","प्त","ष्ट","ष्ठ",       
    "स्र","स्त्र",    "ह्र","हृ","ह्म","ह्य",   "श्च","श्न", 						
    "्य", "्र","्र","्र",                                          
                                                            
    "क्","ख्", "ग्", "घ्","क","ख","ग","घ","ङ",                                
    "च्","ज्","झ्","ञ्","च","छ","ज","झ",                                   
    "ट","ठ","ड","ढ","ण्","ण",                                         
    "त्","थ्", "ध्","न्","त","थ","द","ध","न",                                
    "प्","फ्","ब्","भ्","म्","प","फ","ब","भ","म",                              
                                                            
    "य्", "ल्","व्","श्","ष्", "ळ्", "श्", "स्","ह्",                             
    "य","र","ल","ल","व","श","ष","स","ह","ळ",                              
                                                            
    "औ","ओ","ऑ","आ","अ","ई","इ","उ","ऊ","ऋ","ॠ","ऐ","ए",                    
    
    "ा", "ी","ी", "ीं", "ु","ु","ु","ू","ू", "ृ","ॄ", "ें", "े", "ै","ैं", "ः", "ं","ं","ं","़",		
    "ु","ू","ॅ","ँ","्",                                                       
    
    
    "","े","ै","ओ","आ","औ","ओ","ो","ॉ","ॉ","ो",
    "ुं","े","अ‍ै","ो","अ‍े","ां","अ‍ॅ","ौ","ौ","ृं",
    "ाँ","ूँ","ो","ें","ों","ँ","ँ"," :","ूं"
]

def convert_shree_to_unicode(text: str) -> str:
    # 1. Substitute from mapping arrays
    modified = text
    for one, two in zip(array_one, array_two):
        # We must replace all occurrences
        modified = modified.replace(one, two)
        
    # 2. Reorder chhoti ee matra '{'
    # Find position of '{'
    idx = modified.find("{")
    while idx != -1:
        if idx + 1 < len(modified):
            char_next = modified[idx + 1]
            to_be_replaced = "{" + char_next
            replacement = char_next + "ि"
            modified = modified.replace(to_be_replaced, replacement, 1)
        else:
            # Trailing '{', just replace with empty or keep
            modified = modified.replace("{", "", 1)
        idx = modified.find("{")

    # 3. Handle 'q' matras
    # Regexp replaces
    # JS: /([q])([कखगघङचछजझञटठडड़ढढ़णतथदधनपफबभमयरलवशषसहक़ख़ग़ज़ड़ढ़फ़©])/g -> $2$1
    consonants_pattern = r"([कखगघङचछजझञटठडड़ढढ़णतथदधनपफबभमयरलवशषसहक़ख़ग़ज़ड़ढ़फ़©])"
    modified = re.sub(r"([q])" + consonants_pattern, r"\2\1", modified)
    
    # JS: /([q])(्)([कखगघङचछजझञटठडड़ढढ़णतथदधनपफबभमयरलवशषसहक़ख़ग़ज़ड़ढ़फ़©])/g -> $2$3$1
    modified = re.sub(r"([q])(्)" + consonants_pattern, r"\2\3\1", modified)
    modified = re.sub(r"([q])(्)" + consonants_pattern, r"\2\3\1", modified)
    
    # Replace all remaining 'q' with 'िं'
    modified = modified.replace("q", "िं")

    # 4. Eliminate chhoti ee matra on half-letters
    idx = modified.find("ि्")
    while idx != -1:
        if idx + 2 < len(modified):
            consonant = modified[idx + 2]
            to_replace = "ि्" + consonant
            replacement = "्" + consonant + "ि"
            modified = modified.replace(to_replace, replacement, 1)
        idx = modified.find("ि्")

    # 5. Eliminate chhoti ee matra with anusvara on half-letters
    idx = modified.find("िं्")
    while idx != -1:
        if idx + 3 < len(modified):
            consonant = modified[idx + 3]
            to_replace = "िं्" + consonant
            replacement = "्" + consonant + "िं"
            modified = modified.replace(to_replace, replacement, 1)
        idx = modified.find("िं्")

    # 6. Reorder reph '©'
    set_of_matras = "ािीुूृेैोौं:ँॅ"
    idx = modified.find("©")
    while idx > 0:
        probable = idx - 1
        while probable >= 0 and modified[probable] in set_of_matras:
            probable -= 1
        
        if probable >= 0:
            cluster = modified[probable:idx]
            to_replace = cluster + "©"
            replacement = "र्" + cluster
            modified = modified.replace(to_replace, replacement, 1)
        else:
            # Reph at start, just remove it or keep
            modified = modified.replace("©", "", 1)
        idx = modified.find("©")

    return modified

# Run test
sample_texts = [
    "&& AW gÎmJwê$ gwIam_Or _hmamO H$s OrdZr &&",
    "_madmS>r + [hÝXr",
    "( 1-1 gmIr)"
]

print("Python Console Encoding:", sys.stdout.encoding)
for text in sample_texts:
    result = convert_shree_to_unicode(text)
    print(f"Raw: {repr(text)} -> Unicode: {repr(result)}")
