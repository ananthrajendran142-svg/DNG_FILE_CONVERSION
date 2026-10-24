"""
Builds the standalone, web-connected DGN_Converter.xlsm workbook with embedded VBA macros.
"""

import os
import sys
import win32com.client as win32

EXCEL_PATH = os.path.abspath("DGN_Converter.xlsm")

VBA_CODE = r'''Option Explicit

' ==============================================================================
' DGN TO VECTOR PDF CONVERTER - WEB-CONNECTED EXCEL CLIENT
' ==============================================================================

Public Sub BrowseFile()
    Dim fd As Object
    Set fd = Application.FileDialog(3) ' 3 = msoFileDialogFilePicker
    With fd
        .Title = "Select MicroStation DGN CAD File"
        .Filters.Clear
        .Filters.Add "MicroStation DGN Files (*.dgn)", "*.dgn"
        .Filters.Add "All Files (*.*)", "*.*"
        .AllowMultiSelect = False
        If .Show = -1 Then
            ThisWorkbook.Sheets("Converter").Range("B7").Value = .SelectedItems(1)
            ThisWorkbook.Sheets("Converter").Range("B18").Value = "File selected. Ready to convert."
            ThisWorkbook.Sheets("Converter").Range("B18").Font.Color = RGB(30, 41, 59)
        End If
    End With
End Sub

Public Sub TestConnection()
    Dim serverUrl As String
    serverUrl = Trim(ThisWorkbook.Sheets("Converter").Range("B4").Value)
    If Right(serverUrl, 1) = "/" Then serverUrl = Left(serverUrl, Len(serverUrl) - 1)
    
    ThisWorkbook.Sheets("Converter").Range("B18").Value = "Testing connection to " & serverUrl & "..."
    ThisWorkbook.Sheets("Converter").Range("B18").Font.Color = RGB(37, 99, 235)
    DoEvents
    
    On Error Resume Next
    Dim http As Object
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 5000, 5000, 10000, 10000
    http.Open "GET", serverUrl & "/api/health", False
    http.send
    
    If Err.Number <> 0 Then
        If Application.UserControl Then
            MsgBox "Cannot reach server at:" & vbCrLf & serverUrl & vbCrLf & vbCrLf & _
                   "Error: " & Err.Description & vbCrLf & vbCrLf & _
                   "Please make sure the server URL is correct and running.", vbCritical, "Connection Failed"
        End If
        ThisWorkbook.Sheets("Converter").Range("B18").Value = "Connection failed: Cannot reach server."
        ThisWorkbook.Sheets("Converter").Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    If http.Status = 200 Then
        If Application.UserControl Then
            MsgBox "Server is ONLINE and ready!" & vbCrLf & vbCrLf & _
                   "Connected to: " & serverUrl, vbInformation, "Server Online"
        End If
        ThisWorkbook.Sheets("Converter").Range("B18").Value = ChrW(10003) & " Server is Online and Ready."
        ThisWorkbook.Sheets("Converter").Range("B18").Font.Color = RGB(22, 101, 52)
    Else
        If Application.UserControl Then
            MsgBox "Server responded with HTTP " & http.Status & vbCrLf & http.responseText, vbExclamation, "Unexpected Response"
        End If
        ThisWorkbook.Sheets("Converter").Range("B18").Value = "Server error HTTP " & http.Status
        ThisWorkbook.Sheets("Converter").Range("B18").Font.Color = RGB(220, 38, 38)
    End If
End Sub

Public Sub ConvertToPDF()
    Dim ws As Object
    Set ws = ThisWorkbook.Sheets("Converter")
    
    Dim serverUrl As String, filePath As String, paperChoice As String, themeChoice As String, outFolder As String
    serverUrl = Trim(ws.Range("B4").Value)
    filePath = Trim(ws.Range("B7").Value)
    paperChoice = Trim(ws.Range("B9").Value)
    themeChoice = Trim(ws.Range("B11").Value)
    outFolder = Trim(ws.Range("B13").Value)
    
    If Right(serverUrl, 1) = "/" Then serverUrl = Left(serverUrl, Len(serverUrl) - 1)
    
    ' Validate DGN file
    If filePath = "" Or Dir(filePath) = "" Then
        If Application.UserControl Then MsgBox "Please select a valid .dgn file first.", vbExclamation, "File Not Found"
        ws.Range("B18").Value = "Error: File not found."
        ws.Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    ' Normalize Paper Size
    Dim paperCode As String
    If InStr(1, paperChoice, "A1", vbTextCompare) > 0 Then
        paperCode = "A1"
    ElseIf InStr(1, paperChoice, "A3", vbTextCompare) > 0 Then
        paperCode = "A3"
    ElseIf InStr(1, paperChoice, "A0", vbTextCompare) > 0 Then
        paperCode = "A0"
    ElseIf InStr(1, paperChoice, "Letter", vbTextCompare) > 0 Then
        paperCode = "Letter"
    Else
        paperCode = "A4"
    End If
    
    ' Normalize Theme
    Dim themeCode As String
    If InStr(1, themeChoice, "Blueprint", vbTextCompare) > 0 Then
        themeCode = "blueprint"
    ElseIf InStr(1, themeChoice, "Dark", vbTextCompare) > 0 Then
        themeCode = "dark"
    ElseIf InStr(1, themeChoice, "Cream", vbTextCompare) > 0 Then
        themeCode = "cream"
    Else
        themeCode = "white"
    End If
    
    ' Update status
    ws.Range("B18").Value = "Reading CAD file & uploading..."
    ws.Range("B18").Font.Color = RGB(37, 99, 235)
    DoEvents
    
    ' Read file to Base64
    Dim fileB64 As String
    fileB64 = ReadFileBase64(filePath)
    If fileB64 = "" Then
        If Application.UserControl Then MsgBox "Failed to read DGN file bytes.", vbCritical, "Read Error"
        ws.Range("B18").Value = "Error: Could not read file."
        ws.Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    Dim fileName As String
    fileName = Mid(filePath, InStrRev(filePath, "\") + 1)
    
    ' Construct JSON payload
    Dim payload As String
    payload = "{" & _
              """file_name"": """ & EscapeJson(fileName) & """," & _
              """paper_size"": """ & paperCode & """," & _
              """theme"": """ & themeCode & """," & _
              """file_base64"": """ & fileB64 & """" & _
              "}"
    
    ws.Range("B18").Value = "Converting CAD drawing into vector PDF on server..."
    ws.Range("B18").Font.Color = RGB(37, 99, 235)
    DoEvents
    
    ' Send HTTP request
    On Error Resume Next
    Dim http As Object
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 10000, 15000, 300000, 300000
    http.Open "POST", serverUrl & "/api/convert", False
    http.setRequestHeader "Content-Type", "application/json"
    http.send payload
    
    If Err.Number <> 0 Then
        If Application.UserControl Then MsgBox "HTTP request failed:" & vbCrLf & Err.Description, vbCritical, "Network Error"
        ws.Range("B18").Value = "Network Error: Cannot connect to server."
        ws.Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    If http.Status <> 200 Then
        Dim errResp As String
        errResp = http.responseText
        If Application.UserControl Then
            MsgBox "Server Conversion Error (HTTP " & http.Status & "):" & vbCrLf & vbCrLf & _
                   ExtractJsonVal(errResp, "error"), vbCritical, "Conversion Error"
        End If
        ws.Range("B18").Value = "Error: " & ExtractJsonVal(errResp, "error")
        ws.Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    ' Parse response
    Dim respText As String
    respText = http.responseText
    
    Dim successVal As String
    successVal = ExtractJsonVal(respText, "success")
    If LCase(successVal) <> "true" Then
        If Application.UserControl Then MsgBox "Conversion failed:" & vbCrLf & ExtractJsonVal(respText, "error"), vbCritical, "Failed"
        ws.Range("B18").Value = "Conversion failed."
        ws.Range("B18").Font.Color = RGB(220, 38, 38)
        Exit Sub
    End If
    
    Dim pdfB64 As String, thumbB64 As String, pdfName As String
    pdfB64 = ExtractJsonVal(respText, "pdf_base64")
    thumbB64 = ExtractJsonVal(respText, "preview_base64")
    pdfName = ExtractJsonVal(respText, "pdf_filename")
    If pdfName = "" Then pdfName = Left(fileName, InStrRev(fileName, ".") - 1) & ".pdf"
    
    ' Determine output path
    Dim saveDir As String
    If outFolder <> "" And Dir(outFolder, vbDirectory) <> "" Then
        saveDir = outFolder
    Else
        saveDir = Left(filePath, InStrRev(filePath, "\") - 1)
    End If
    If Right(saveDir, 1) <> "\" Then saveDir = saveDir & "\"
    
    Dim finalPdfPath As String
    finalPdfPath = saveDir & pdfName
    
    ' Save PDF file (via streaming download or fallback base64)
    Dim dlUrl As String
    dlUrl = ExtractJsonVal(respText, "download_url")
    Dim pdfSaved As Boolean
    pdfSaved = False
    
    If dlUrl <> "" Then
        ws.Range("B18").Value = "Downloading converted vector PDF..."
        ws.Range("B18").Font.Color = RGB(37, 99, 235)
        DoEvents
        
        Dim httpDl As Object
        Set httpDl = CreateObject("MSXML2.ServerXMLHTTP.6.0")
        httpDl.setTimeouts 10000, 15000, 120000, 120000
        httpDl.Open "GET", serverUrl & dlUrl, False
        httpDl.send
        If httpDl.Status = 200 Then
            Dim streamOut As Object
            Set streamOut = CreateObject("ADODB.Stream")
            streamOut.Type = 1 ' adTypeBinary
            streamOut.Open
            streamOut.Write httpDl.responseBody
            streamOut.SaveToFile finalPdfPath, 2 ' adSaveCreateOverWrite
            streamOut.Close
            pdfSaved = True
        End If
    End If
    
    If Not pdfSaved And pdfB64 <> "" Then
        WriteBase64File pdfB64, finalPdfPath
        pdfSaved = True
    End If
    
    ' Extract metadata
    Dim dgnVer As String, vecCount As String, timeSec As String, outSize As String
    dgnVer = ExtractJsonVal(respText, "dgn_version")
    vecCount = ExtractJsonVal(respText, "vector_elements_count")
    timeSec = ExtractJsonVal(respText, "total_time_seconds")
    outSize = ExtractJsonVal(respText, "output_size_formatted")
    
    ' Update Results Card
    ws.Range("B18").Value = ChrW(10003) & " Successfully converted in " & timeSec & "s!"
    ws.Range("B18").Font.Color = RGB(22, 101, 52)
    ws.Range("B19").Value = dgnVer
    ws.Range("B20").Value = vecCount & " elements"
    ws.Range("B21").Value = timeSec & " s (" & outSize & ")"
    
    ' Hyperlink to PDF
    ws.Hyperlinks.Add Anchor:=ws.Range("B22"), Address:=finalPdfPath, TextToDisplay:=pdfName
    ws.Range("B22").Font.Underline = 2 ' xlUnderlineStyleSingle
    ws.Range("B22").Font.Color = RGB(37, 99, 235)
    
    ' Update Live Drawing Preview
    If thumbB64 <> "" Then
        Dim tempImg As String
        tempImg = Environ("TEMP") & "\dgn_preview_" & Format(Now, "hhmmss") & ".png"
        WriteBase64File thumbB64, tempImg
        
        Dim shp As Object
        For Each shp In ws.Shapes
            If shp.Name = "LiveCADPreview" Then shp.Delete
        Next shp
        
        Dim targetBox As Object
        Set targetBox = ws.Range("E4:K24")
        Dim pic As Object
        Set pic = ws.Shapes.AddPicture(tempImg, 0, 1, targetBox.Left + 8, targetBox.Top + 8, -1, -1)
        pic.Name = "LiveCADPreview"
        pic.LockAspectRatio = 1
        
        Dim maxW As Double, maxH As Double
        maxW = targetBox.Width - 16
        maxH = targetBox.Height - 16
        
        If pic.Width > maxW Then
            pic.Width = maxW
        End If
        If pic.Height > maxH Then
            pic.Height = maxH
        End If
        
        ' Center inside targetBox
        pic.Left = targetBox.Left + (targetBox.Width - pic.Width) / 2
        pic.Top = targetBox.Top + (targetBox.Height - pic.Height) / 2
        pic.Line.Color.RGB = RGB(148, 163, 184)
        pic.Line.Weight = 1
        
        On Error Resume Next
        Kill tempImg
        On Error GoTo 0
    End If
    
    If Application.UserControl Then
        MsgBox "Drawing converted successfully!" & vbCrLf & vbCrLf & _
               "File: " & pdfName & vbCrLf & _
               "Saved to: " & finalPdfPath & vbCrLf & _
               "Vectors: " & vecCount & " elements" & vbCrLf & _
               "Time: " & timeSec & "s", vbInformation, "Conversion Complete"
    End If
End Sub

Public Sub OpenOutputPDF()
    Dim ws As Object
    Set ws = ThisWorkbook.Sheets("Converter")
    Dim linkAddr As String
    If ws.Range("B22").Hyperlinks.Count > 0 Then
        linkAddr = ws.Range("B22").Hyperlinks(1).Address
        If Dir(linkAddr) <> "" Then
            Dim wsh As Object
            Set wsh = CreateObject("WScript.Shell")
            wsh.Run """" & linkAddr & """"
            Exit Sub
        End If
    End If
    If Application.UserControl Then MsgBox "No converted PDF available to open yet. Please convert a DGN file first.", vbExclamation, "No PDF"
End Sub

Private Function ReadFileBase64(ByVal filePath As String) As String
    On Error GoTo ErrHandler
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 1 ' adTypeBinary
    stream.Open
    stream.LoadFromFile filePath
    
    Dim domDoc As Object, node As Object
    Set domDoc = CreateObject("MSXML2.DOMDocument.6.0")
    Set node = domDoc.createElement("b64")
    node.DataType = "bin.base64"
    node.nodeTypedValue = stream.Read
    
    Dim res As String
    res = Replace(node.Text, vbLf, "")
    res = Replace(res, vbCr, "")
    ReadFileBase64 = res
    
    stream.Close
    Exit Function
ErrHandler:
    ReadFileBase64 = ""
End Function

Private Sub WriteBase64File(ByVal base64Str As String, ByVal outPath As String)
    Dim domDoc As Object, node As Object
    Set domDoc = CreateObject("MSXML2.DOMDocument.6.0")
    Set node = domDoc.createElement("b64")
    node.DataType = "bin.base64"
    node.Text = base64Str
    
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 1 ' adTypeBinary
    stream.Open
    stream.Write node.nodeTypedValue
    stream.SaveToFile outPath, 2 ' 2 = adSaveCreateOverWrite
    stream.Close
End Sub

Private Function ExtractJsonVal(ByVal json As String, ByVal key As String) As String
    Dim pattern As String
    pattern = """" & key & """\s*:\s*""([^""]+)"""
    
    Dim reg As Object, matches As Object
    Set reg = CreateObject("VBScript.RegExp")
    reg.Pattern = pattern
    reg.IgnoreCase = True
    reg.Global = False
    
    If reg.Test(json) Then
        Set matches = reg.Execute(json)
        ExtractJsonVal = matches(0).SubMatches(0)
        Exit Function
    End If
    
    ' Fallback for numbers or booleans (unquoted)
    pattern = """" & key & """\s*:\s*([^,\}\]]+)"
    reg.Pattern = pattern
    If reg.Test(json) Then
        Set matches = reg.Execute(json)
        ExtractJsonVal = Trim(matches(0).SubMatches(0))
        Exit Function
    End If
    
    ExtractJsonVal = ""
End Function

Private Function EscapeJson(ByVal s As String) As String
    s = Replace(s, "\\", "\\\\")
    s = Replace(s, """", "\\""")
    s = Replace(s, vbCr, "\\r")
    s = Replace(s, vbLf, "\\n")
    s = Replace(s, vbTab, "\\t")
    EscapeJson = s
End Function
'''

def create_workbook():
    excel = win32.gencache.EnsureDispatch('Excel.Application')
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb = excel.Workbooks.Add()
        ws = wb.ActiveSheet
        ws.Name = "Converter"
        excel.ActiveWindow.DisplayGridlines = False
        ws.PageSetup.Orientation = 2  # xlLandscape
        ws.PageSetup.Zoom = False
        ws.PageSetup.FitToPagesWide = 1
        ws.PageSetup.FitToPagesTall = 1

        # Apply Global Fonts and Palette
        ws.Cells.Font.Name = "Segoe UI"
        ws.Cells.Font.Size = 10

        # Colors
        C_NAVY = 0x2A170F      # BGR for #0F172A
        C_WHITE = 0xFFFFFF
        C_SLATE_BG = 0xF8FAFC  # Background
        C_CARD_BG = 0xFFFFFF
        C_TEXT_MAIN = 0x1E293B
        C_TEXT_MUTED = 0x64748B
        C_BORDER = 0xE2E8F0
        C_BLUE_BTN = 0xEB6325  # BGR for #2563EB

        # Set Column Widths
        ws.Columns("A").ColumnWidth = 3
        ws.Columns("B").ColumnWidth = 46
        ws.Columns("C").ColumnWidth = 6
        ws.Columns("D").ColumnWidth = 3
        ws.Columns("E").ColumnWidth = 14
        ws.Columns("F").ColumnWidth = 14
        ws.Columns("G").ColumnWidth = 14
        ws.Columns("H").ColumnWidth = 14
        ws.Columns("I").ColumnWidth = 14
        ws.Columns("J").ColumnWidth = 14
        ws.Columns("K").ColumnWidth = 14

        # -------------------------------------------------------------
        # Header Banner
        # -------------------------------------------------------------
        header = ws.Range("B2:K2")
        header.Merge()
        header.Value = "📐  MicroStation DGN to Vector PDF Converter"
        header.Font.Size = 16
        header.Font.Bold = True
        header.Font.Color = C_WHITE
        header.Interior.Color = C_NAVY
        header.RowHeight = 44
        header.HorizontalAlignment = -4108  # xlCenter
        header.VerticalAlignment = -4108

        # -------------------------------------------------------------
        # Configuration Section (Left Pane)
        # -------------------------------------------------------------
        def set_label(cell_ref, text):
            c = ws.Range(cell_ref)
            c.Value = text
            c.Font.Bold = True
            c.Font.Size = 9
            c.Font.Color = C_TEXT_MUTED

        def set_input(cell_ref, default_val=""):
            c = ws.Range(cell_ref)
            c.Value = default_val
            c.Font.Size = 10
            c.Font.Color = C_TEXT_MAIN
            c.Interior.Color = 0xF1F5F9  # Light gray fill
            c.Borders.Color = C_BORDER
            c.RowHeight = 22
            c.VerticalAlignment = -4108

        # Server API URL
        set_label("B3", "SERVER API ENDPOINT URL")
        set_input("B4", "http://localhost:5000")

        # DGN File Path
        set_label("B6", "MICROSTATION DGN DRAWING FILE (.dgn)")
        set_input("B7", "")

        # Paper Size
        set_label("B8", "PAPER SIZE")
        set_input("B9", "A1 Architectural (Recommended)")
        # Dropdown validation for Paper Size
        val_paper = ws.Range("B9").Validation
        val_paper.Delete()
        val_paper.Add(3, 1, 1, "A1 Architectural (Recommended),A4 Standard,A3 Standard,A0 Large Format,US Letter")

        # Theme
        set_label("B10", "COLOR THEME")
        set_input("B11", "White (Standard Clean)")
        # Dropdown validation for Theme
        val_theme = ws.Range("B11").Validation
        val_theme.Delete()
        val_theme.Add(3, 1, 1, "White (Standard Clean),Blueprint Blue,Dark CAD Station,Architectural Cream")

        # Output Folder
        set_label("B12", "OUTPUT FOLDER (LEAVE EMPTY FOR DEFAULT)")
        set_input("B13", "")

        # -------------------------------------------------------------
        # Results & Metadata Section
        # -------------------------------------------------------------
        set_label("B17", "CONVERSION STATUS")
        status_cell = ws.Range("B18")
        status_cell.Value = "Ready to convert. Choose a file and click 'Convert to PDF'."
        status_cell.Font.Size = 10
        status_cell.Font.Bold = True
        status_cell.Font.Color = C_TEXT_MUTED
        status_cell.Interior.Color = 0xF8FAFC
        status_cell.Borders.Color = C_BORDER
        status_cell.RowHeight = 22
        status_cell.VerticalAlignment = -4108

        ws.Range("B19").Value = "DGN Version: —"
        ws.Range("B19").Font.Size = 9
        ws.Range("B19").Font.Color = C_TEXT_MUTED

        ws.Range("B20").Value = "Vector Count: —"
        ws.Range("B20").Font.Size = 9
        ws.Range("B20").Font.Color = C_TEXT_MUTED

        ws.Range("B21").Value = "Performance: —"
        ws.Range("B21").Font.Size = 9
        ws.Range("B21").Font.Color = C_TEXT_MUTED

        set_label("B22", "OUTPUT PDF FILE")
        ws.Range("B22").Value = "—"
        ws.Range("B22").Font.Size = 10

        # -------------------------------------------------------------
        # Drawing Preview Frame (Right Pane, E4:K24)
        # -------------------------------------------------------------
        prev_header = ws.Range("E3:K3")
        prev_header.Merge()
        prev_header.Value = "LIVE DRAWING PREVIEW"
        prev_header.Font.Bold = True
        prev_header.Font.Size = 9
        prev_header.Font.Color = C_TEXT_MUTED

        prev_box = ws.Range("E4:K24")
        prev_box.Merge()
        prev_box.Interior.Color = 0x0F172A  # Dark CAD background
        prev_box.Borders.Color = C_BORDER
        prev_box.Value = "Converted drawing preview will appear here."
        prev_box.Font.Color = 0x94A3B8
        prev_box.Font.Size = 11
        prev_box.HorizontalAlignment = -4108
        prev_box.VerticalAlignment = -4108

        # -------------------------------------------------------------
        # Add VBA Buttons
        # -------------------------------------------------------------
        # Button 1: Browse File (Row 7, Column C)
        btn_browse = ws.Buttons().Add(ws.Range("C7").Left + 2, ws.Range("C7").Top + 1, 48, 20)
        btn_browse.Caption = "Browse"
        btn_browse.OnAction = "BrowseFile"

        # Button 2: Test Server Connection (Row 4, Column C)
        btn_test = ws.Buttons().Add(ws.Range("C4").Left + 2, ws.Range("C4").Top + 1, 48, 20)
        btn_test.Caption = "Test"
        btn_test.OnAction = "TestConnection"

        # Button 3: Convert to PDF (Primary Action Button below inputs)
        btn_convert = ws.Buttons().Add(ws.Range("B15").Left, ws.Range("B15").Top, ws.Range("B15").Width, 28)
        btn_convert.Caption = "Convert DGN to Vector PDF"
        btn_convert.Font.Bold = True
        btn_convert.Font.Size = 11
        btn_convert.OnAction = "ConvertToPDF"

        # Button 4: Open PDF
        btn_open = ws.Buttons().Add(ws.Range("B23").Left, ws.Range("B23").Top, ws.Range("B23").Width, 24)
        btn_open.Caption = "Open Converted PDF"
        btn_open.OnAction = "OpenOutputPDF"

        # -------------------------------------------------------------
        # Inject VBA Code Module
        # -------------------------------------------------------------
        vb_comp = wb.VBProject.VBComponents.Add(1)  # 1 = vbext_ct_StdModule
        vb_comp.CodeModule.AddFromString(VBA_CODE)

        # Save as Macro-Enabled Workbook (.xlsm, format code 52)
        if os.path.exists(EXCEL_PATH):
            try:
                os.remove(EXCEL_PATH)
            except OSError:
                pass

        wb.SaveAs(EXCEL_PATH, 52)
        print(f"Successfully generated: {EXCEL_PATH}")

    finally:
        wb.Close(SaveChanges=False)
        excel.Quit()

if __name__ == "__main__":
    create_workbook()
