@echo off
chcp 65001 >nul
title Nettoyeur de texte
echo =========================================
echo       Nettoyage des balises
echo =========================================

:: Verifie si un fichier a bien ete glisse-depose
if "%~1"=="" (
    echo.
    echo Erreur : Aucun fichier fourni.
    echo Utilisation : Glissez et deposez votre fichier directement sur l'icone de ce script.
    echo.
    pause
    exit /b
)

:: Definition des variables pour les passer a PowerShell
set "IN=%~1"
set "OUT=%~dpn1_propre%~x1"

echo.
echo Nettoyage en cours du fichier : "%~nx1"...

:: Execution du remplacement avec PowerShell
:: [char]34 est utilise pour generer les guillemets (") sans casser le script Batch
powershell -Command "$texte = [IO.File]::ReadAllText($env:IN); $texte = $texte.Replace('{\an2}', '').Replace('<font color='+[char]34+'#ffffff'+[char]34+'>', '').Replace('</font>', ''); [IO.File]::WriteAllText($env:OUT, $texte, [System.Text.Encoding]::UTF8)"

echo.
echo Termine !
echo Le fichier nettoye a ete cree ici :
echo "%OUT%"
echo.
pause