Attribute VB_Name = "Module3_POtext"
'@Folder "Modules"
Sub SearchPOtext()
    
    File_Name = Application.ThisWorkbook.Name
    Search_PO_Text.Protect Contents:=False
    ProcessDataPO_Text.Protect Contents:=False
    
    'Clear Search Results
    Set ClrRange = Search_PO_Text.Range("B8:J1048576")
    ClrRange.ClearContents
    ActiveSheet.Calculate
    Application.Wait (Now + TimeValue("0:00:01"))
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    
    'Validate Search
    If InStr(Search_PO_Text.Range("F4").Value, "'") <> 0 Then
        MsgBox "Search cannot contain an apostrophe", Title:="Invalid Seach"
        Exit Sub
    End If
        If Search_PO_Text.Range("F4").Value = "" Then
        MsgBox "Please fill in search criteria", Title:="Invalid Seach"
        Exit Sub
    End If
    
    For PlantIndex = 1 To 2
        'Clear Process Data
        Set ClrRange = ProcessDataPO_Text.Range("B8:F1048576")
        ClrRange.ClearContents
        
        'Search Phrase
        SearchPhrase = Search_PO_Text.Range("F4").Value
        SearchPhrase = Replace(SearchPhrase, "*", "%")
        
        'Set Connection to Whitewater Database
        Set oCon = New ADODB.Connection
        If PlantIndex = 1 Then
            oCon.ConnectionString = "Provider=Microsoft.ace.OLEDB.12.0; Data Source=" & "\\USLXA-P-FS01\kansas_city\Distributed Information SOURCE\Long Description Search\PAC1 SAP Long Description Search.accdb" & ";"
        Else
            oCon.ConnectionString = "Provider=Microsoft.ace.OLEDB.12.0; Data Source=" & "\\USLXA-P-FS01\kansas_city\Distributed Information SOURCE\Long Description Search\SAP Long Description Search.accdb" & ";"
        End If
        oCon.Open
    
        'Read Data from Whitewater Database
        Set oRS = New ADODB.Recordset
        oRS.ActiveConnection = oCon
        oRS.Source = "SELECT DISTINCT [Material Number] FROM [Long Description] WHERE [Long Description] LIKE '%" & SearchPhrase & "%' ORDER BY [Material Number];"
        oRS.Open
        Set ClrRange = ProcessDataPO_Text.Range("B8:B1048576")
        ClrRange.ClearContents
        ClrRange.CopyFromRecordset oRS
    
        lastRow = ProcessDataPO_Text.Cells(Rows.Count, 2).End(xlUp).Row
        
        Set ClrRange = ProcessDataPO_Text.Range("D8:F1048576")
        ClrRange.ClearContents
        
        For i = 8 To lastRow
            SearchPhrase = ProcessDataPO_Text.Cells(i, 2).Value
                
            oRS.Close
            oRS.Source = "SELECT DISTINCT [Material Number], [Desc Line], [Long Description] FROM [Long Description] WHERE [Material Number] LIKE '%" & SearchPhrase & "%' ORDER BY [Material Number], [Desc Line];"
            oRS.Open
            FirstOpenRow = ProcessDataPO_Text.Cells(Rows.Count, 4).End(xlUp).Row + 1
            AppendSearch = "D" & FirstOpenRow & ":F1048576"
            Set ClrRange = ProcessDataPO_Text.Range(AppendSearch)
            ClrRange.ClearContents
            ClrRange.CopyFromRecordset oRS
        Next i
               
        lastRow = ProcessDataPO_Text.Cells(Rows.Count, 4).End(xlUp).Row
        
        'Format for display
        POtext = ""
        OldVNum = ProcessDataPO_Text.Cells(8, 4).Value
        For i = 8 To lastRow + 1
            If ProcessDataPO_Text.Cells(i, 4).Value = OldVNum Then
                POtext = POtext & ProcessDataPO_Text.Cells(i, 6).Value & Chr(10)
            Else
                While ((Right(POtext, 1) = " ") Or (Right(POtext, 1) = Chr(10)))
                    POtext = Left(POtext, (Len(POtext) - 1))
                Wend
                POtext = Replace(POtext, "Â", "")
                If PlantIndex = 1 Then
                    PlantColOffset = 0
                    FirstOpenRow = Search_PO_Text.Cells(Rows.Count, 2 + PlantColOffset).End(xlUp).Row + 1
                    AppendDesc = "B" & FirstOpenRow
                Else
                    PlantColOffset = 6
                    FirstOpenRow = Search_PO_Text.Cells(Rows.Count, 2 + PlantColOffset).End(xlUp).Row + 1
                    AppendDesc = "H" & FirstOpenRow
                End If
                Search_PO_Text.Cells(FirstOpenRow, 2 + PlantColOffset).Value = OldVNum
                If PlantIndex = 1 Then
                    Search_PO_Text.Cells(FirstOpenRow, 3 + PlantColOffset).Value = "=IF(" & AppendDesc & "="""","""",INDEX(WHI_Materials!$B:$B,MATCH(SUBSTITUTE(" & AppendDesc & ",""."",""""),WHI_Materials!$A:$A,0)))"
                Else
                    Search_PO_Text.Cells(FirstOpenRow, 3 + PlantColOffset).Value = "=IF(" & AppendDesc & "="""","""",INDEX(SAB_Materials!$B:$B,MATCH(SUBSTITUTE(" & AppendDesc & ",""."",""""),SAB_Materials!$A:$A,0)))"
                End If
                Search_PO_Text.Cells(FirstOpenRow, 4 + PlantColOffset).Value = POtext
                OldVNum = ProcessDataPO_Text.Cells(i, 4).Value
                POtext = ProcessDataPO_Text.Cells(i, 6).Value & Chr(10)
            End If
    
        Next i
        oRS.Close
        If Not oRS Is Nothing Then Set oRS = Nothing
        If Not oCon Is Nothing Then Set oCon = Nothing
    
    Next PlantIndex
        
    'Clear Process Data
    Set ClrRange = ProcessDataPO_Text.Range("B8:F1048576")
    ClrRange.ClearContents
    
    Search_PO_Text.Columns("B").ColumnWidth = 12
    Search_PO_Text.Columns("C").ColumnWidth = 44
    Search_PO_Text.Columns("D").ColumnWidth = 51
    Search_PO_Text.Columns("H").ColumnWidth = 12
    Search_PO_Text.Columns("I").ColumnWidth = 44
    Search_PO_Text.Columns("J").ColumnWidth = 51
    Search_PO_Text.Rows("8:1048576").AutoFit
            
    ActiveWindow.ScrollColumn = 1
    ActiveWindow.ScrollRow = 8
    
    Search_PO_Text.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    ProcessDataPO_Text.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
End Sub

Sub ClearSearchPO()
    File_Name = Application.ThisWorkbook.Name
    Search_PO_Text.Protect Contents:=False
    ProcessDataPO_Text.Protect Contents:=False
    
    'Clear Parts
    Set ClrRange = Search_PO_Text.Range("B8:J1048576")
    ClrRange.ClearContents
    
    'Search Phrase
    Search_PO_Text.Range("F4").Value = ""
    
    'Clear Process Data
    Set ClrRange = ProcessDataPO_Text.Range("B8:F1048576")
    ClrRange.ClearContents
    
    'Set Column Width
    Search_PO_Text.Columns("B").ColumnWidth = 12
    Search_PO_Text.Columns("C").ColumnWidth = 44
    Search_PO_Text.Columns("D").ColumnWidth = 51
    Search_PO_Text.Columns("H").ColumnWidth = 12
    Search_PO_Text.Columns("I").ColumnWidth = 44
    Search_PO_Text.Columns("J").ColumnWidth = 51
    
    Search_PO_Text.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    ProcessDataPO_Text.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
End Sub

