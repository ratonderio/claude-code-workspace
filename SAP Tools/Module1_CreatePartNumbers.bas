Attribute VB_Name = "Module1_CreatePartNumbers"
'@Folder "Modules"

'TESTING FLAG
Public Testing_Flag As Boolean



Public i As Long, J As Long, DnLn As Long, DB_Col As Long, DB_Row As Long, RevType As Long, MajorRev As Long, MinorRev As Long
Public Ord As Long, Ignore As Long, ActiveYr As Long, DescLen As Long, NextLine As Long, NewInteger As Long, lastRow As Long, IndexHier As Long, LastRowWorking As Long
Public TotalLines As Long, TotalOrders As Long, SearchOrd As Long, Jmax As Long, Imax As Long, NewLong As Long, ExtendCol As Long, IndexWorking As Long
Public PrevOrd As Long, LineNum As Long, PrevLine As Long, PC_Num As Long, PCnum As Long, ConfMon As Long, ConfYr As Long
Public Index As Long, IndexNext As Long, SAPIndex As Long, StoreIndex As Long, StoreBoardIndex As Long
Public BOM_VertPos As Long, FI1 As Long, FI2 As Long, BOM_Items As Long, BOM_IndexMax As Long, Part_Index As Long
Public Index28 As Long, SAP_MaxLimit As Long, FirstEmptyRow As Long, BOM_Balloon As Long, EndlessLoopCounter As Long, ImportIndex As Long
Public OthelloPlayerTurn As Long, RowIndex As Long, ColumnIndex As Long, DeltaIndex As Long, P1Count As Long, P2Count As Long, OtherOthelloPlayerTurn As Long, Answer As Long
Public ActiveTurnRow As Long, ActiveTurnColumn As Long, SurroundingRow As Long, SurroundingColumn As Long, DeltaColumn As Long, DeltaRow As Long, MaxIndex As Long
Public RT_Row As Long, RT_Column As Long, Winner As Long, WinningScore As Long, LosingScore As Long, CompFlipCount As Long, VTC_Row As Long, VTC_Column As Long
Public DeltaRowValue As Long, DeltaColumnValue As Long, ColorChangeRow As Long, ColorChangeColumn As Long, ColorChangeIndex As Long, PlayerNum As Long, FlipMax As Long
Public CompMaxIndex As Long, RandIndex As Long, CompRow As Long, CompColumn As Long, TurnNum As Long
Public Connect4PlayerTurn As Long, ColChkIndex As Long, StartRow As Long, StartCol As Long, NumInARow As Long, Index4 As Long, C4Row As Long, C4Col As Long, TopRowIndex As Long
Public FirstOpenRow As Long, PlantIndex As Long, PlantColOffset As Long
'
Public NewRevDate As Date, RevDate As Date
'
Public CurrentRev As String, RevStr As String, ExtendValue As String, WorkingRange As String, AssyStr As String
Public V_Number As String, V_NumDesc As String, V_NumProcess As String, PartType As String, StoreLoc As String, MFG_Info As String
Public NextB0 As String, B0Num As String, StorageCode As String, ProdHier As String, ProdHierCode As String, C_Number As String
Public CreateInfoRecord As String, File_Name As String, UserName As String, InfoRecordRev As String, V_NumExists As String, ProjNum As String
Public BOM_V_Number As String, BOM_Part_V_Num As String, ObsPart As String, BypassChecking As String, PO_Text As String, PO_TextString As String
Public ImportFile As String, ImportFileName As String, ImportSheetName As String, ModeType As String, BOM_TxtLn As String
Public NewRevDesc As String, NewRevNum As String, RevNum As String, GameSelect As String, ShtName As String, InfoRecordCreatedForStr As String
Public SearchPhrase As String, AppendSearch As String, AppendDesc As String, OldVNum As String, POtext As String, SparePart As String
'
Public BOM_Part_Qty As Double
'
Public Flag_SAP As Boolean, Flag_StoreLoc As Boolean, Flag_FieldsMissing As Boolean
Public Flag_Hierarchy As Boolean, Flag_C_Num As Boolean, Flag_DescLen As Boolean, Flag_MFG_Len As Boolean, Flag_PartExists As Boolean
Public Flag_BOM_NA As Boolean, Flag_EnterBOM As Boolean, Flag_BOM_PartNA As Boolean
Public ValidTurn As Boolean, ValidSurrounding As Boolean, P1ValidTurn As Boolean, P2ValidTurn As Boolean, GameOver As Boolean, ValidBool As Boolean
Public Flag_C4GameOver As Boolean, Flag_C4TieGame As Boolean, TiedGame As Boolean
'
Public ClrRange As Range, RevRange As Range, BoardRange As Range, CompCalcRange As Range, SavedBoard As Range, StoreBoard As Range
'
Public session As GuiSession
Public SAPconnection As GuiConnection

Public Const WkBk = ".xlsm"
Public Const Sht1 = ""

Public Const serverName As String = "USLXA-P-SQL01.cps.local"
Public Const databaseName As String = "PAC1CPE"
Public Const databaseUserID As String = "dash"
Public Const databasePassword As String = "manage_DB"

'Public Const serverName As String = "PAC5Intra03\PAC5SQLExpress"
'Public Const databaseName As String = "PAC1CPE"
'Public Const databaseUserID As String = "sa"
'Public Const databasePassword As String = "manage_ERP"

Public Const databaseConnectionString As String = "Driver={SQL Server};Server=" _
& serverName & ";Database=" & databaseName & ";User ID=" & databaseUserID _
& ";Password=" & databasePassword & ";"

Sub Sequence()
Attribute Sequence.VB_ProcData.VB_Invoke_Func = " \n14"
        
    'Reset Error Checks
    Flag_SAP = False
    Flag_StoreLoc = False
    Flag_Hierarchy = False
    Flag_C_Num = False
    Flag_DescLen = False
    Flag_MFG_Len = False
    Flag_FieldsMissing = False
        
    'Get Workbook Name
    File_Name = Application.ThisWorkbook.Name
    UserName = UCase(Environ("Username"))
    CreatePartNumbers.Protect Contents:=False
    PartHistory.Protect Contents:=False
    
    Set ClrRange = ProcessDataCPN.Range("L6:L103")
    ClrRange.ClearContents
    
    Call InitiateSAP
    
    For Index = 5 To 103
        Flag_PartExists = False
        IndexNext = Index + 1
        If UCase(CreatePartNumbers.Cells(Index, 2).Value) <> "YES" Then
            V_Number = UCase(CreatePartNumbers.Cells(Index, 3).Value)
        Else
            V_Number = UCase(ProcessDataCPN.Cells(Index, 12).Value)
        End If
        ProjNum = CreatePartNumbers.Cells(Index, 4).Value
        C_Number = UCase(CreatePartNumbers.Cells(Index, 5).Value)
        InfoRecordRev = UCase(CreatePartNumbers.Cells(Index, 6).Value)
        V_NumDesc = CreatePartNumbers.Cells(Index, 7).Value
        MFG_Info = CreatePartNumbers.Cells(Index, 8).Value
        PartType = CreatePartNumbers.Cells(Index, 9).Value
        StoreLoc = CreatePartNumbers.Cells(Index, 10).Value
        ProdHier = CreatePartNumbers.Cells(Index, 11).Value
        CreateInfoRecord = CreatePartNumbers.Cells(Index, 12).Value
        SparePart = CreatePartNumbers.Cells(Index, 13).Value
        PO_Text = CreatePartNumbers.Cells(Index, 14).Value
        NextB0 = CreatePartNumbers.Cells(IndexNext, 2).Value

        'Makse Sure V# is Capital
        If CreatePartNumbers.Cells(Index, 3).Value <> V_Number Then
            CreatePartNumbers.Cells(Index, 3).Value = V_Number
        End If
        
        'Make sure C# is Capital
        If CreatePartNumbers.Cells(Index, 5).Value <> C_Number Then
            CreatePartNumbers.Cells(Index, 5).Value = C_Number
        End If
            
        'Info Record Rev
        'Remove Extra Spaces
        While Right(InfoRecordRev, 1) = " "
            InfoRecordRev = Left(InfoRecordRev, (Len(InfoRecordRev) - 1))
        Wend
        If InfoRecordRev = "" Then
            InfoRecordRev = "A"
        End If
        
        'Description
        'Remove Extra Spaces
        While Right(V_NumDesc, 1) = " "
            V_NumDesc = Left(V_NumDesc, (Len(V_NumDesc) - 1))
        Wend
        'Description Length Check
        If Len(V_NumDesc) > 40 Then
            Flag_DescLen = True
            Exit For
        End If
        
        'MFG Info
        'Remove Extra Spaces
        While Right(MFG_Info, 1) = " "
            MFG_Info = Left(MFG_Info, (Len(MFG_Info) - 1))
        Wend
        'MFG Length Check
        If Len(MFG_Info) > 30 Then 'Check Length
            Flag_MFG_Len = True
            Exit For
        End If
        
        'Check For Complete
        If V_NumDesc = "" Then
            If Index = 5 Then
                Flag_FieldsMissing = True
            End If
            Exit For
        End If
        If PartType = "" Then
            If Index = 5 Then
                Flag_FieldsMissing = True
            End If
            Exit For
        End If
        If StoreLoc = "" Then
            If Index = 5 Then
                Flag_FieldsMissing = True
            End If
            Exit For
        End If
        If ProdHier = "" Then
            If Index = 5 Then
                Flag_FieldsMissing = True
            End If
            Exit For
        End If
        If CreateInfoRecord = "" Then
            If Index = 5 Then
                Flag_FieldsMissing = True
            End If
            Exit For
        End If
        
        'Check If C#/S# is Needed
        If C_Number = "" Then
            If (UCase(CreateInfoRecord) <> "NO") Then
                Flag_C_Num = True
                Exit For
            End If
        End If
        
        'Extract the Storage Location code
        StorageCode = Left(Right(StoreLoc, 5), 4)
        If ((StorageCode <> "A111") _
        And (StorageCode <> "A112") _
        And (StorageCode <> "A113") _
        And (StorageCode <> "A114") _
        And (StorageCode <> "A115") _
        And (StorageCode <> "A116") _
        And (StorageCode <> "A117") _
        And (StorageCode <> "A118") _
        And (StorageCode <> "A119") _
        And (StorageCode <> "A120") _
        And (StorageCode <> "A121") _
        And (StorageCode <> "A122") _
        And (StorageCode <> "A123") _
        And (StorageCode <> "A212")) Then
            Flag_StoreLoc = True
            Exit For
        End If
        
        'Set the Product Hierarchy Code
        lastRow = Dropdowns.Cells(Rows.Count, 8).End(xlUp).Row
        Flag_Hierarchy = True
        ProdHierCode = ""
        For IndexHier = 3 To lastRow
            If UCase(ProdHier) = UCase(Dropdowns.Cells(IndexHier, 8).Value) Then
                ProdHierCode = Dropdowns.Cells(IndexHier, 9).Value
                Flag_Hierarchy = Flase
                Exit For
            End If
        Next IndexHier
        If Flag_Hierarchy = True Then
            Exit For
        End If

        'Call Routines
        Call SAP_ZJ61
        If Flag_PartExists = False Then
            If UCase(CreateInfoRecord) = "YES" Then
                Call SAP_CV01N
            End If
            Call SAP_MM02
        End If
        
        'V# Info
        CreatePartNumbers.Cells(Index, 3).Value = V_Number 'Enter the new Part Number
        If UCase(NextB0) = "YES" Then 'Set up for next B0#
            B0Num = ProcessDataCPN.Cells(IndexNext, 2).Value
            If B0Num < 10 Then
                ProcessDataCPN.Cells(IndexNext, 12).Value = Left(V_Number, 10) & B0Num
            ElseIf ((B0Num > 9) And (B0Num < 100)) Then
                ProcessDataCPN.Cells(IndexNext, 12).Value = Left(V_Number, 9) & B0Num
            End If
        End If
        
        If ((Flag_SAP <> True) And (Flag_PartExists <> True)) Then
            Application.ScreenUpdating = False
            Call StoreInDatabase
            Call UpdateMaterials
            Application.ScreenUpdating = True
        End If
        
    Next Index

    Set ClrRange = ProcessDataCPN.Range("L6:L103")
    ClrRange.ClearContents
    
    Application.ScreenUpdating = False
    Call ReadFromDatabase
    Application.ScreenUpdating = True
    
    CreatePartNumbers.Activate
    
    If ((Flag_SAP = False) And (Flag_StoreLoc = False) And (Flag_Hierarchy = False) And (Flag_C_Num = False) And (Flag_DescLen = False) And (Flag_MFG_Len = False) And (Flag_PartExists = False) And (Flag_FieldsMissing = False)) Then
        MsgBox "Part Numbers Created", Title:="Finished"
    ElseIf Flag_SAP = True Then
        MsgBox "Part Numbers Were Not Created" + vbCr + "Could Not Establish SAP", Title:="Process Failed"
    ElseIf Flag_StoreLoc = True Then
        MsgBox "Bad Storage Location", Title:="Process Failed"
    ElseIf Flag_Hierarchy = True Then
        MsgBox "Bad Product Hierarchy", Title:="Process Failed"
    ElseIf Flag_C_Num = True Then
        MsgBox "C#/S# Required", Title:="Process Failed"
    ElseIf Flag_DescLen = True Then
        MsgBox "Description Cannot Exceed 40 Characters", Title:="Process Failed"
    ElseIf Flag_MFG_Len = True Then
        MsgBox "MFG Info Cannot Exceed 30 Characters", Title:="Process Failed"
    ElseIf Flag_FieldsMissing = True Then
        MsgBox "Part Numbers Were Not Created" & Chr(10) & "Please Fill in all Required Fields", Title:="Missing Fields"
    ElseIf Flag_PartExists = True Then
        MsgBox "Part " & V_NumExists & " already exists in SAP", Title:="Process Failed"
        V_NumExists = ""
    Else
        MsgBox "Part Numbers Were Not Created", Title:="Process Failed"
    End If

    CreatePartNumbers.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    PartHistory.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
End Sub

Sub InitiateSAP()

    'Reset the session Connections
    On Error Resume Next
        If Not SAPconnection Is Nothing Then Set SAPconnection = Nothing
        If Not session Is Nothing Then Set session = Nothing
    On Error GoTo 0
    
    'Check if logged on and initiate the connection
    On Error GoTo SAP_NotLoggedIn
        Set SAPconnection = GetObject("SAPGUI").GetScriptingEngine.Children(0)
    On Error GoTo 0
    
StartLookingForEasyAccess:
    'Find Number of instances (children) open
    NumOfWindowsSAP = SAPconnection.Sessions.Count
    'Seach for an initial "SAP Easy Access" Screen
    For SAPIndex = 0 To NumOfWindowsSAP - 1
         If InStr(1, (SAPconnection.Children(CInt(SAPIndex)).FindById("wnd[0]").Text), "SAP Easy Access") Then
             Set session = SAPconnection.Children(CInt(SAPIndex))
             Exit For
         End If
     Next SAPIndex
     
     'If a session is not established (None of the instances are "SAP Easy Access")
     If session Is Nothing Then
        'If a new instance can be open
        If NumOfWindowsSAP < 6 Then
            SAPconnection.Sessions.Item(0).CreateSession
            While NumOfWindowsSAP = SAPconnection.Sessions.Count
            Wend
            GoTo StartLookingForEasyAccess
        'At max instances, cause an error
        Else
            MsgBox "Cannot connect to SAP. Open an ""SAP Easy Access"" window to run the program.", Title:="Error!"
            End
        End If
     End If

    Exit Sub
    
SAP_NotLoggedIn:
    MsgBox "Please sign into SAP to continue", Title:="Error!"
    End
End Sub

Sub SAP_CV01N()

    session.FindById("wnd[0]").maximize
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "CV01N" 'Create Info Record
    session.FindById("wnd[0]").SendVKey 0
    If V_Number = "" Then
        session.FindById("wnd[0]/usr/ctxtDRAW-DOKNR").Text = "WB"
    Else
        session.FindById("wnd[0]/usr/ctxtDRAW-DOKNR").Text = V_Number
    End If
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKAR").Text = "GRP"
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKTL").Text = "000"
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKVR").Text = "00"
    session.FindById("wnd[0]").SendVKey 0
    'Info Record Exists: Go to edit
    On Error GoTo EditInfoRecord
        session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSMAIN/ssubSCR_MAIN:SAPLCV110:0102/txtDRAT-DKTXT").Text = V_NumDesc 'Fill in Description
    On Error GoTo 0
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSMAIN/ssubSCR_MAIN:SAPLCV110:0102/ctxtDRAW-LABOR").Text = "111"

    'Create Link if it does not exist
    On Error GoTo CreateLink
        session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSMAIN/ssubSCR_MAIN:SAPLCV110:0102/cntlCTL_FILES1/shellcont/shell/shellcont[1]/shell").selectNode "          1"
    On Error GoTo 0
 
    ' If New V#
    If V_Number = "" Then
        V_NumProcess = session.FindById("wnd[0]/usr/ctxtDRAW-DOKNR").Text
        V_Number = Left(V_NumProcess, 7) & "." & Right(V_NumProcess, 3)
    Else
         
    End If
    
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS").Select
    If (C_Number = "") Then
        session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS/ssubSCR_MAIN:SAPLCTMS:4000/sub:SAPLCTMS:4000/ctxtRCTMS-MWERT[2,32]").Text = V_Number
    Else
        On Error GoTo OpenAddnlData
            session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS/ssubSCR_MAIN:SAPLCTMS:4000/sub:SAPLCTMS:4000/ctxtRCTMS-MWERT[2,32]").Text = C_Number
        On Error GoTo 0
    End If
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS/ssubSCR_MAIN:SAPLCTMS:4000/sub:SAPLCTMS:4000/ctxtRCTMS-MWERT[3,32]").Text = InfoRecordRev
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS/ssubSCR_MAIN:SAPLCTMS:4000/sub:SAPLCTMS:4000/ctxtRCTMS-MWERT[1,32]").Text = "1110"
    session.FindById("wnd[0]/tbar[0]/btn[11]").Press 'Save
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press 'Back
    Exit Sub
    
OpenAddnlData:
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSCLASS").Select
    Resume
    
CreateLink:
    session.FindById("wnd[0]/usr/tabsTAB_MAIN/tabpTSMAIN/ssubSCR_MAIN:SAPLCV110:0102/btnPB_FILE_CREATE").Press
    session.FindById("wnd[1]").SendVKey 0
    session.FindById("wnd[1]").SendVKey 0
    Resume Next
    
EditInfoRecord:
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press 'Back
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "CV02N" 'Create Part Number
    session.FindById("wnd[0]").SendVKey 0
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKNR").Text = V_Number
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKAR").Text = "GRP"
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKTL").Text = "000"
    session.FindById("wnd[0]/usr/ctxtDRAW-DOKVR").Text = "00"
    session.FindById("wnd[0]").SendVKey 0
    Resume

End Sub

Sub SAP_ZJ61()
    
    session.FindById("wnd[0]").maximize
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "ZJ61" 'Create Part Number
    session.FindById("wnd[0]").SendVKey 0
    
    On Error Resume Next 'Needed when the plant field is blank
    session.FindById("wnd[1]/usr/ctxtMARC-WERKS").Text = 1111
    session.FindById("wnd[1]/usr/ctxtMVKE-VKORG").Text = 1140
    session.FindById("wnd[1]/tbar[0]/btn[0]").Press
    On Error GoTo 0
    
    'Verify the Plant is 1111
    If session.FindById("wnd[0]/usr/ctxtMARC-WERKS").Text <> 1111 Then
        session.FindById("wnd[0]/tbar[1]/btn[13]").Press
        session.FindById("wnd[1]/usr/ctxtMARC-WERKS").Text = 1111
        session.FindById("wnd[1]/usr/ctxtMVKE-VKORG").Text = 1140

        session.FindById("wnd[1]/tbar[0]/btn[0]").Press
    End If

    If V_Number = "" Then
        session.FindById("wnd[0]/usr/ctxtMARA-MATNR").Text = "WB"
    Else
        session.FindById("wnd[0]/usr/ctxtMARA-MATNR").Text = V_Number
    End If
    
    'Select Part Type
    If PartType = "Purchased To Order (Ind)" Then 'Purchase Part (10)
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 2
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(2).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 4
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(4).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 14
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(14).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 0
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(0).Selected = True
    ElseIf PartType = "Make To Order (Ind)" Then 'Make Part (30)
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 0
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(0).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 4
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(4).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 14
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(14).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 2
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(2).Selected = True
    ElseIf PartType = "Phantom Assembly" Then 'Phantom Assembly (50)
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 0
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(0).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 2
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(2).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 14
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(14).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 4
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(4).Selected = True
    ElseIf PartType = "Supply Item" Then 'Supply Item (150)
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 0
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(0).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 2
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(2).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 4
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(4).Selected = False
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").VerticalScrollbar.Position = 14
        session.FindById("wnd[0]/usr/tblSAPMZJ61_PROCESSTC_A").GetAbsoluteRow(14).Selected = True
    End If

    session.FindById("wnd[0]/tbar[1]/btn[5]").Press
    
    'Check if part exists
    If Left(GetObject("SAPGUI").GetScriptingEngine.Children(0).Children(SAPIndex + 0).FindById("wnd[0]").Text, 3) = "SAP" Then
        Flag_PartExists = True
        V_NumExists = V_Number
        session.FindById("wnd[0]/tbar[0]/btn[3]").Press 'Back
        Exit Sub
    End If
    
    'Create Part: Enter Info
    session.FindById("wnd[0]/usr/ctxtZJ61_D1100-LGFSB").Text = StorageCode
    session.FindById("wnd[0]/usr/ctxtZJ61_D1100-PRODH").Text = ProdHierCode
    session.FindById("wnd[0]/usr/txtZJ61_D1100-MAKTX1").Text = V_NumDesc
    session.FindById("wnd[0]/usr/txtZJ61_D1100-MAKTX2").Text = V_NumDesc
    If SparePart <> "" Then
        session.FindById("wnd[0]/usr/ctxtZJ61_D1100-MVGR3").Text = Left(SparePart, 1)
    End If
    
    session.FindById("wnd[0]/tbar[0]/btn[11]").Press 'Save
    session.FindById("wnd[1]/tbar[0]/btn[0]").Press 'Enter
    If V_Number = "" Then
        V_Number = session.FindById("wnd[0]/usr/ctxtMARA-MATNR").Text
    End If
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press 'Back

End Sub

Sub SAP_MM02()
    
    session.FindById("wnd[0]").maximize
    
    'Enter info
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "MM02"
    session.FindById("wnd[0]").SendVKey 0
    session.FindById("wnd[0]/usr/ctxtRMMG1-MATNR").Text = V_Number
    session.FindById("wnd[0]/tbar[1]/btn[5]").Press 'Select Screens
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(0).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(6).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(9).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(11).Selected = True
    session.FindById("wnd[1]/tbar[0]/btn[6]").Press 'Set Org Settings
    session.FindById("wnd[1]/usr/ctxtRMMG1-WERKS").Text = "1111"
    session.FindById("wnd[1]/usr/ctxtRMMG1-LGORT").Text = StorageCode
    session.FindById("wnd[1]/usr/ctxtRMMG1-VKORG").Text = "1140"
    session.FindById("wnd[1]/usr/ctxtRMMG1-VTWEG").Text = "VK"
    session.FindById("wnd[1]/tbar[0]/btn[0]").Press
    
    'Assign Info Record
    If UCase(CreateInfoRecord) = "YES" Then
        session.FindById("wnd[0]/tbar[1]/btn[27]").Press
        session.FindById("wnd[1]/usr/subSCREEN:SAPLCV140:0204/tblSAPLCV140SUB_DOC/ctxtDRAW-DOKAR[0,0]").Text = "GRP"
        session.FindById("wnd[1]/usr/subSCREEN:SAPLCV140:0204/tblSAPLCV140SUB_DOC/ctxtDRAW-DOKNR[1,0]").Text = V_Number
        session.FindById("wnd[1]").SendVKey 0
        session.FindById("wnd[1]/tbar[0]/btn[8]").Press
    End If
        
    'Modify if Schenck
    If UCase(MFG_Info) = "SCHENCK" Then
        MFG_Info = "Schenck: " & V_Number
        CreatePartNumbers.Cells(Index, 8).Value = MFG_Info
    End If
    session.FindById("wnd[0]/usr/subSUB6:SAPLZZ_MGD1:0001/txtMARA-ZZ_TEILENUMMER").Text = MFG_Info
    
    ' Remove BackFlush
    If UCase(StoreLoc) = "WAREHOUSE (A111)" Then 'Warehouse
    session.FindById("wnd[0]/mbar/menu[2]/menu[12]").Select
        On Error Resume Next 'Needed when giving the plant number is necessary upon viewing the MDP2 screen
        session.FindById("wnd[1]/usr/ctxtRMMG1-WERKS").Text = "1111"
        session.FindById("wnd[1]/usr/ctxtRMMG1-LGORT").Text = StorageCode
        session.FindById("wnd[1]/usr/ctxtRMMG1-VKORG").Text = "1140"
        session.FindById("wnd[1]/usr/ctxtRMMG1-VTWEG").Text = "VK"
        session.FindById("wnd[1]/tbar[0]/btn[0]").Press
        On Error GoTo 0
    session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2484/ctxtMARC-RGEKZ").Text = ""
    Else
    End If
    
    'Sales Text
    session.FindById("wnd[0]/mbar/menu[2]/menu[7]").Select
        On Error Resume Next 'Needed when giving the plant number is necessary upon viewing the Sales Text screen
        session.FindById("wnd[1]/tbar[0]/btn[0]").Press
        session.FindById("wnd[1]/usr/ctxtRMMG1-WERKS").Text = "1111"
        session.FindById("wnd[1]/usr/ctxtRMMG1-LGORT").Text = StorageCode
        session.FindById("wnd[1]/usr/ctxtRMMG1-VKORG").Text = "1140"
        session.FindById("wnd[1]/usr/ctxtRMMG1-VTWEG").Text = "VK"
        session.FindById("wnd[1]/tbar[0]/btn[0]").Press
        On Error GoTo 0
    session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2121/cntlLONGTEXT_VERTRIEBS/shellcont/shell").Text = V_NumDesc
    
    'Purchase Order Text
    session.FindById("wnd[0]/mbar/menu[2]/menu[10]").Select
        On Error Resume Next 'Needed when giving the plant number is necessary upon viewing the Purchase Order Text screen
        session.FindById("wnd[1]/usr/ctxtRMMG1-WERKS").Text = "1111"
        session.FindById("wnd[1]/usr/ctxtRMMG1-LGORT").Text = StorageCode
        session.FindById("wnd[1]/usr/ctxtRMMG1-VKORG").Text = "1140"
        session.FindById("wnd[1]/usr/ctxtRMMG1-VTWEG").Text = "VK"
        session.FindById("wnd[1]/tbar[0]/btn[0]").Press
        On Error GoTo 0
    
    'Purchase Order Text String
    PO_TextString = V_NumDesc
    If MFG_Info <> "" Then
        PO_TextString = PO_TextString + vbCr + MFG_Info
    End If
    If PO_Text <> "" Then
        PO_TextString = PO_TextString + vbCr + PO_Text
    End If
    session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2321/cntlLONGTEXT_BESTELL/shellcont/shell").Text = PO_TextString
    
    session.FindById("wnd[0]/tbar[0]/btn[11]").Press
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press

End Sub

Sub ClearTableCPN()
    File_Name = Application.ThisWorkbook.Name
    CreatePartNumbers.Protect Contents:=False
    CreatePartNumbers.Range("B5:N103").ClearContents
    CreatePartNumbers.Cells(5, "B").Value = "N/A"
    CreatePartNumbers.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
End Sub

Sub UpdateMaterials()
    File_Name = Application.ThisWorkbook.Name
    'Find the first empty row
    FirstEmptyRow = ((WHI_Materials.Cells(WHI_Materials.Rows.Count, "A").End(xlUp).Row) + 1)
    WHI_Materials.Cells(FirstEmptyRow, 1).Value = Replace(V_Number, ".", "")
    WHI_Materials.Cells(FirstEmptyRow, 2).Value = V_NumDesc
End Sub

Sub StoreInDatabase()

    'Set Database Connection
    Set oCon = New ADODB.Connection
    oCon.ConnectionString = databaseConnectionString ' Trusted_Connection=yes;"
    oCon.Open

    V_NumDesc = Replace(V_NumDesc, "'", Chr(94)) 'check for "'"
    MFG_Info = Replace(MFG_Info, "'", Chr(94)) 'check for "'"
    
    'Create String to Write to Database
    AssyStr = "'" & Now & "', '"                           ' Date Stamp
    AssyStr = AssyStr & UserName & "', '"                  ' User Login
    AssyStr = AssyStr & V_Number & "', '"                  ' V Number
    AssyStr = AssyStr & C_Number & "', '"                  ' C Number
    AssyStr = AssyStr & ProjNum & "', '"                   ' Project Number
    AssyStr = AssyStr & V_NumDesc & "', '"                 ' Description
    AssyStr = AssyStr & MFG_Info & "', '"                  ' Mfg Info
    AssyStr = AssyStr & PartType & "', '"                  ' Part Type
    AssyStr = AssyStr & StoreLoc & "', '"                  ' Storage Location
    AssyStr = AssyStr & ProdHier & "'"                     ' Product Hierarchy
    
    'Write to database
    Set oRS = New ADODB.Recordset
    oRS.ActiveConnection = oCon
    oRS.Source = "INSERT INTO SAP_Tool_History(uniqID, Date_Stamp, UserLogin, V_Num, CorS_Num, Proj_Num, Descrip, Mfg_Num, Part_Type, Store_Loc, Prod_Hier) VALUES(newid(), " & AssyStr & ")"
    oRS.Open

    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing

End Sub

Sub ReadFromDatabase()
    
    File_Name = Application.ThisWorkbook.Name
    PartHistory.Protect Contents:=False
    
    'Set Database Connection
    Set oCon = New ADODB.Connection
    oCon.ConnectionString = databaseConnectionString ' Trusted_Connection=yes;"
    oCon.Open
    
    'Read Data
    Set oRS = New ADODB.Recordset
    oRS.ActiveConnection = oCon
    oRS.Source = "SELECT SAP_Tool_History.Date_Stamp, UserLogin, V_Num, CorS_Num, Proj_Num, Descrip, Mfg_Num, Part_Type, Store_Loc, Prod_Hier FROM SAP_Tool_History ORDER BY SAP_Tool_History.Date_Stamp DESC;"
    oRS.Open
    Set ClrRange = PartHistory.Range("B4:K1048576")
    ClrRange.ClearContents
    ClrRange.CopyFromRecordset oRS

    oRS.Close
    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing
    
    PartHistory.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
End Sub

Sub GetMakeParts()

    File_Name = Application.ThisWorkbook.Name
    MakeParts.Protect Contents:=False
    ProjNum = MakeParts.Cells(3, 3).Value

    'Project Number: Remove Extra Spaces
    While Right(ProjNum, 1) = " "
        ProjNum = Left(ProjNum, (Len(ProjNum) - 1))
    Wend

    'Set Database Connection
    Set oCon = New ADODB.Connection
    oCon.ConnectionString = databaseConnectionString ' Trusted_Connection=yes;"
    oCon.Open
    
    'Read Data
    Set oRS = New ADODB.Recordset
    oRS.ActiveConnection = oCon
    
    If ProjNum = "" Then
        oRS.Source = "SELECT SAP_Tool_History.V_Num, Proj_Num, UserLogin, Date_Stamp, CorS_Num, Descrip, Store_Loc, Prod_Hier, Make_Created FROM SAP_Tool_History WHERE SAP_Tool_History.Part_Type = '" & "Make To Order (Ind)" & "' AND Make_Created Is NULL ORDER BY SAP_Tool_History.V_Num;"
    Else
        oRS.Source = "SELECT SAP_Tool_History.V_Num, Proj_Num, UserLogin, Date_Stamp, CorS_Num, Descrip, Store_Loc, Prod_Hier, Make_Created FROM SAP_Tool_History WHERE SAP_Tool_History.Part_Type = '" & "Make To Order (Ind)" & "' AND Proj_Num = '" & ProjNum & "' AND Make_Created Is NULL ORDER BY SAP_Tool_History.V_Num;"
    End If
    oRS.Open
    Set ClrRange = MakeParts.Range("B6:J1048576")
    ClrRange.ClearContents
    ClrRange.CopyFromRecordset oRS

    oRS.Close
    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing
    
    ActiveWindow.ScrollColumn = 1
    ActiveWindow.ScrollRow = 6
    
    MakeParts.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
End Sub

Sub UpdateMakeParts()
    File_Name = Application.ThisWorkbook.Name
    MakeParts.Protect Contents:=False
    
    'Set Database Connection
    Set oCon = New ADODB.Connection
    oCon.ConnectionString = databaseConnectionString ' Trusted_Connection=yes;"
    oCon.Open
    
    'Read Data
    Set oRS = New ADODB.Recordset
    oRS.ActiveConnection = oCon
    
    lastRow = MakeParts.Cells(Rows.Count, 2).End(xlUp).Row
    
    For Index = 6 To lastRow
        If UCase(MakeParts.Cells(Index, 10).Value) = "YES" Then
            V_Number = UCase(MakeParts.Cells(Index, 2).Value)
            
            oRS.Source = "UPDATE SAP_Tool_History SET SAP_Tool_History.Make_Created='" & "Yes" & "' WHERE SAP_Tool_History.V_Num='" & V_Number & "'"
            oRS.Open
            
        End If
    Next Index
    
    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing
    
    Call GetMakeParts
End Sub

Sub IncrementRev()
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    
    File_Name = Application.ThisWorkbook.Name
    Revisions.Protect Contents:=False
    
    CurrentRev = Revisions.Range("B5").Value
    MajorRev = Left(CurrentRev, InStr(CurrentRev, "."))
    MinorRev = Right(CurrentRev, Len(CurrentRev) - InStr(CurrentRev, "."))
    
    'Custom Message Box
    Dim cC As clsMsgbox
    Dim iR As Integer
    
    Set cC = New clsMsgbox
    iR = cC.MessageBoxEx("Major = " & MajorRev + 1 & ".0" & Chr(10) & "Minor = " & MajorRev & "." & MinorRev + 1, , "Revision Type?", "Major Rev", "Minor Rev", "&Cancel")
    If iR = Button1 Then
        MajorRev = MajorRev + 1
        RevStr = MajorRev & ".0"
    ElseIf iR = Button2 Then
        MinorRev = MinorRev + 1
        RevStr = MajorRev & "." & MinorRev
    ElseIf iR = Button3 Then
        Exit Sub
    End If
    
    Set RevRange = Revisions.Range("B5:D1048575")
    RevRange.Copy
    Revisions.Cells(6, 2).PasteSpecial Paste:=xlPasteValues, _
        Operation:=xlNone, SkipBlanks:=False, Transpose:=False
    Set ClrRange = Revisions.Range("B5:D5")
    ClrRange.ClearContents
    
    Revisions.Range("B5").Value = RevStr
    Revisions.Range("C5").Value = Date
    Revisions.Range("D5").Value = "• "
    Revisions.Range("D5").Select
    Revisions.Columns("B:D").AutoFit
    ActiveWindow.ScrollColumn = 1
    ActiveWindow.ScrollRow = 1
    
    Revisions.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
End Sub

Sub SubmitRev()

    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    
    File_Name = Application.ThisWorkbook.Name
    CreatePartNumbers.Protect Contents:=False
    
    On Error GoTo CannotFindRevFile1
        Workbooks.Open Filename:="\\USWWQ-P-FS01\cadfiles\SapTools\Archive\SAP Tools Rev History.xlsm"
    On Error GoTo 0
    
    Set ClrRange = Workbooks("SAP Tools Rev History.xlsm").Worksheets("RevHistory").Range("C5:E1048576")
    ClrRange.ClearContents
    Set RevRange = Revisions.Range("B5:D1048576")
    RevRange.Copy
    Workbooks("SAP Tools Rev History.xlsm").Worksheets("RevHistory").Cells(5, 3).PasteSpecial Paste:=xlPasteValues, _
        Operation:=xlNone, SkipBlanks:=False, Transpose:=False
        
    Application.DisplayAlerts = True
    Workbooks("SAP Tools Rev History.xlsm").Save
    Workbooks("SAP Tools Rev History.xlsm").Close
    
    'Adjust Rev Details
    RevNum = Revisions.Cells(5, 2).Value
    RevDate = Revisions.Cells(5, 3).Value
    NewRevDesc = Revisions.Cells(5, 4).Value
    CreatePartNumbers.Cells(2, 2).Value = "Revision: " & RevNum & " (" & RevDate & ")"
    CreatePartNumbers.Cells(2, 2).Font.Italic = True
    CreatePartNumbers.Cells(2, 2).Font.ThemeColor = xlThemeColorDark1
    CreatePartNumbers.Cells(2, 2).Font.TintAndShade = -0.499984740745262
    On Error Resume Next
    CreatePartNumbers.Range("B2").Select
    With Selection.Validation
        .Delete
        .Add Type:=xlValidateInputOnly, AlertStyle:=xlValidAlertStop, Operator _
        :=xlBetween
        .IgnoreBlank = True
        .InCellDropdown = True
        .InputTitle = "Latest Revision: " & RevNum & " (" & RevDate & ")"
        .ErrorTitle = ""
        .InputMessage = NewRevDesc
        .ErrorMessage = ""
        .ShowInput = True
        .ShowError = True
    End With
    On Error GoTo 0
    
    Revisions.Visible = False
    'Reset Create Part Numbers Sheet
    CreatePartNumbers.Activate
    Call ClearTableCPN
    Range("Z105").Select
    ActiveWindow.ScrollColumn = 1
    ActiveWindow.ScrollRow = 5
    ActiveWorkbook.Protect Structure:=True, Windows:=False
    CreatePartNumbers.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    
    Application.ScreenUpdating = True
    MsgBox "Revision " & Revisions.Range("B5").Value & " has been successfully submitted", Title:="Revision Submitted!"
    
    Exit Sub
    
CannotFindRevFile1:
    MsgBox "Cannot Find Rev File", Title:="Error!"
End Sub

Sub AdjustHierDropdown()

    File_Name = Application.ThisWorkbook.Name
    CreatePartNumbers.Protect Contents:=False
    
    lastRow = Dropdowns.Cells(Rows.Count, 8).End(xlUp).Row
    WorkingRange = "=Dropdowns!$H$3:$H$" & lastRow

    With CreatePartNumbers.Range("K5:K103").Validation
        .Delete
        .Add Type:=xlValidateList, AlertStyle:=xlValidAlertStop, Operator:= _
        xlBetween, Formula1:=WorkingRange
        .IgnoreBlank = True
        .InCellDropdown = True
        .InputTitle = ""
        .ErrorTitle = ""
        .InputMessage = ""
        .ErrorMessage = ""
        .ShowInput = True
        .ShowError = True
    End With
    
    CreatePartNumbers.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    MsgBox "Product Hierarchy Entered"
    
End Sub

Sub UpdateCreatedBy()
    File_Name = Application.ThisWorkbook.Name
    OldUser = "L.HANLEY"
    NewUser = "LY.HANLEY"
    'Set Database Connection
    Set oCon = New ADODB.Connection
    oCon.ConnectionString = databaseConnectionString ' Trusted_Connection=yes;"
    oCon.Open
    
    'Read Data
    Set oRS = New ADODB.Recordset
    oRS.ActiveConnection = oCon
            
            oRS.Source = "UPDATE SAP_Tool_History SET SAP_Tool_History.UserLogin='" & NewUser & "' WHERE SAP_Tool_History.UserLogin='" & OldUser & "'"
            oRS.Open
    
    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing
    
    Call ReadFromDatabase
End Sub

Sub UpdateDesc(V_Number As String, NewDesc As String)
'
'    V_Number = "W016936.B02"
'    NewDesc = "CTRL,2FDR,PWM,N4X,DD,115V,90VDC,316SS,UL"
    
    Dim update
    
    
    'Set Database Connection
    Set oCon = New ADODB.Connection: oCon.ConnectionString = databaseConnectionString: oCon.Open
    
    'Read Data
    Set oRS = New ADODB.Recordset
    
    oRS.ActiveConnection = oCon
            
            oRS.Source = "UPDATE SAP_Tool_History SET SAP_Tool_History.Descrip='" & NewDesc & "' WHERE SAP_Tool_History.V_Num='" & V_Number & "'"
            oRS.Open
    
    If Not oRS Is Nothing Then Set oRS = Nothing
    If Not oCon Is Nothing Then Set oCon = Nothing
    
    Call ReadFromDatabase
End Sub

Sub Unprotect_All()

    ThisWorkbook.Protect Structure:=False
    
    'Visible Sheets
    CreatePartNumbers.Visible = True
    ProcessDataCPN.Visible = True
    PartHistory.Visible = True
    BOM_Creation.Visible = True
    ProcessDataBOM.Visible = True
    ProcessRoutingBOM.Visible = True
    WHI_Materials.Visible = True
    SAB_Materials.Visible = True
    Dropdowns.Visible = True
    
    'Protect Sheets
    CreatePartNumbers.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    ProcessDataCPN.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    PartHistory.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    BOM_Creation.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    ProcessDataBOM.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    ProcessRoutingBOM.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    Dropdowns.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True

End Sub

Sub Protect_All()

    'Visible Sheets
    CreatePartNumbers.Visible = True
    ProcessDataCPN.Visible = False
    PartHistory.Visible = True
    BOM_Creation.Visible = True
    ProcessDataBOM.Visible = False
    ProcessRoutingBOM.Visible = False
    WHI_Materials.Visible = True
    SAB_Materials.Visible = True
    Dropdowns.Visible = False
    
    'Protect Sheets
    CreatePartNumbers.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    ProcessDataCPN.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    PartHistory.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    ProcessRoutingBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    Dropdowns.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowSorting:=True, AllowFiltering:=True
    ActiveWorkbook.Protect Structure:=True, Windows:=False
End Sub
