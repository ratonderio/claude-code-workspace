Attribute VB_Name = "Module2_BOM"
'@Folder "Modules"
Dim CS02_Flag As Boolean

Const F_Item_Number As String = "RC29P-POSNR"    'Text Field
Const F_Material_Number As String = "RC29P-IDNRK" 'CText Field
Const F_Material_Description As String = "RC29P-KTEXT" 'Text Field
Const F_Material_Quantity As String = "RC29P-MENGE" 'Text Field
Const F_Item_ID As String = "RC29P-IDENT"        'Text Field
Const F_Table_Valid_Rows As String = "RC29P-ENTRY" 'Text Field

Const F_Text_Field As String = "GuiTextField"
Const F_CText_Field As String = "GuiCTextField"

Const T_CS02_Table As String = "usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT"

Sub Default_Or_PE_BOM()

    Dim Response As String                       'Is this a custom BOM?
    Dim Response2 As String                      'Continue with standard BOM?
    
    Response = MsgBox("Is this a PE Custom BOM?", vbQuestion + vbYesNo, "Standard or Custom BOM?")
    
    If Response = vbYes Then
        BOMCreation.Show
    ElseIf Response = vbNo Then
        Response2 = MsgBox("Continue with Standard BOM?", vbQuestion + vbYesNo, "Continue?")
        If Response2 = vbYes Then
            SAP_CS01
        End If
    Else
        Debug.Print "Broken"
    End If


End Sub

Sub SAP_CS01()

    CS02_Flag = False
    
    'Get Workbook Name
    File_Name = Application.ThisWorkbook.Name
    BOM_Creation.Protect Contents:=False
    ProcessDataBOM.Protect Contents:=False
    
    'Reset Error Checks
    Flag_EnterBOM = False
    Flag_BOM_NA = False
    Flag_BOM_PartNA = False
    EndlessLoopCounter = 0
    BypassChecking = BOM_Creation.Cells(4, 10).Value
    
    'Error Check: V# missing
    BOM_V_Number = UCase(BOM_Creation.Cells(4, 3).Value)
    If BOM_V_Number = "" Then
        MsgBox "Enter a B.O.M. to create", Title:="Error! No V#"
        BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        Exit Sub
    End If
    
    'Error Check: V# not active
    If UCase(BypassChecking) <> "YES" Then
        If IsError(BOM_Creation.Cells(4, 4).Value) Then
            MsgBox "B.O.M. " & BOM_V_Number & " is not active in SAP", Title:="Error: V# not Active!"
            BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
            ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
            Exit Sub
        End If
    End If
    
    'Error Check Obsolete
    If Not (IsError(BOM_Creation.Cells(4, 4).Value)) Then
        If ((Left((BOM_Creation.Cells(4, 4).Value), 1) = "*") _
            Or (Left((BOM_Creation.Cells(4, 4).Value), 5) = "(OBS)") _
            Or (Left((BOM_Creation.Cells(4, 4).Value), 8) = "OBSOLETE")) Then
            ObsPart = UCase(BOM_Creation.Cells(4, 3).Value)
            MsgBox ObsPart & " is obsolete", Title:="Error: Obsolete V#!"
            BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
            ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
            Exit Sub
        End If
    End If
    
    For Index = 7 To 506
        'Error Check: BOM Part missing
        If UCase(BypassChecking) <> "YES" Then
            If ((IsError(BOM_Creation.Cells(Index, 4).Value)) And (UCase(BOM_Creation.Cells(Index, 6).Value) <> "TEXT")) Then
                MsgBox "Not all B.O.M. components are active in SAP", Title:="Error: B.O.M. Component not Active!"
                BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                Exit Sub
            End If
        End If
        
        'Error Check Bad Quantity
        If UCase(BOM_Creation.Cells(Index, 3).Value) <> "" Then
            If ((BOM_Creation.Cells(Index, 5).Value = "") Or (BOM_Creation.Cells(Index, 5).Value = "0")) Then
                MsgBox "B.O.M. quantities must be a numerical value and cannot be 0 or blank", Title:="Error: Bad Quantity!"
                BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                Exit Sub
            End If
        End If
        
        'Error Check Obsolete
        If Not (IsError(BOM_Creation.Cells(Index, 4).Value)) Then
        
            If ((Left((BOM_Creation.Cells(Index, 4).Value), 1) = "*") _
                Or (Left((BOM_Creation.Cells(Index, 4).Value), 5) = "(OBS)") _
                Or (Left((BOM_Creation.Cells(Index, 4).Value), 8) = "OBSOLETE")) Then
                ObsPart = UCase(BOM_Creation.Cells(Index, 3).Value)
                MsgBox "Part " & ObsPart & " is obsolete", Title:="Error: Obsolete Part!"
                BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
                Exit Sub
            End If
            
        End If
        
    Next Index
    
    BOM_VertPos = 0
    
    FilterBOM
    InitiateSAP

    session.FindById("wnd[0]").maximize
    
    'CS01 Create Bom
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nCS01"
    session.FindById("wnd[0]").SendVKey 0
    session.FindById("wnd[0]/usr/ctxtRC29N-MATNR").Text = BOM_V_Number
    session.FindById("wnd[0]/usr/ctxtRC29N-WERKS").Text = "1111"
    session.FindById("wnd[0]/usr/ctxtRC29N-STLAN").Text = "1"
    session.FindById("wnd[0]").SendVKey 0
    
    'CS01 Failed, CS02 Start
    If (session.FindById("wnd[0]/sbar/pane[0]").Text <> "") Then
        Dim Response As String
        Dim msgText As String
        
        msgText = "SAP Status Text: " & session.FindById("wnd[0]/sbar/pane[0]").Text
        msgText = msgText & vbNewLine & "CS01 Create BOM Failed (Usually due to a BOM already existing)"
        msgText = msgText & vbNewLine & "Do you want to continue to CS02 Change BOM?"
        msgText = msgText & vbNewLine & "THIS WILL REMOVE ALL ITEMS ON THE EXISTING BOM."
        Response = MsgBox(msgText, vbCritical + vbYesNo, "Modify Existing BOM?")
        
        If (Response = vbNo) Then
            session.FindById("wnd[0]/tbar[0]/btn[15]").Press
            Exit Sub
        ElseIf (Response = vbYes) Then
            session.FindById("wnd[0]/tbar[0]/btn[15]").Press
            SAP_CS02
        End If
        
    End If


    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    '                           TODO CHANGE TO NEW METHOD
    '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    'Chunks of B.O.M.
    SAP_MaxLimit = FindSapMaxBomRow(session)
    
    '52, 22, 8   52-8 = 44, 44/22 = 2
    
    BOM_IndexMax = (BOM_Items - (BOM_Items Mod SAP_MaxLimit)) / SAP_MaxLimit
    If (BOM_Items Mod SAP_MaxLimit) = 0 Then
        BOM_IndexMax = BOM_IndexMax - 1
    End If
    
    For Index = 0 To BOM_IndexMax
        EndlessLoopCounter = 0
        BOM_VertPos = Index * SAP_MaxLimit
        On Error GoTo PressEnter
        'Set Vertical Entry Position
        
        session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT").VerticalScrollbar.Position = BOM_VertPos
        'Fill in chunck of B.O.M.
        For Index28 = 0 To (SAP_MaxLimit - 1)
            Part_Index = (SAP_MaxLimit * Index) + 7 + Index28
            
            If ProcessDataBOM.Cells(Part_Index, 3).Value <> "" Then
                On Error GoTo -1
                BOM_Balloon = ProcessDataBOM.Cells(Part_Index, 2).Value
                BOM_Part_V_Num = UCase(ProcessDataBOM.Cells(Part_Index, 3).Value)
                BOM_Part_Qty = ProcessDataBOM.Cells(Part_Index, 4).Value
                BOM_TxtLn = UCase(ProcessDataBOM.Cells(Part_Index, 5).Value)
                On Error GoTo PressEnter
                session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT/txtRC29P-POSNR[0," & Index28 & "]").Text = BOM_Balloon
                session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT/txtRC29P-MENGE[4," & Index28 & "]").Text = BOM_Part_Qty
                If BOM_TxtLn = "TEXT" Then
                    session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT/ctxtRC29P-POSTP[1," & Index28 & "]").Text = "T"
                    session.FindById("wnd[0]").SendVKey 0 'Enter
                    session.FindById("wnd[0]/usr/subPOS_PDAT:SAPLCSDI:0840/txtRC29P-POTX1").Text = BOM_Part_V_Num
                Else
                    session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT/ctxtRC29P-IDNRK[2," & Index28 & "]").Text = BOM_Part_V_Num
                End If
            Else
                session.FindById("wnd[0]").SendVKey 0 'Enter
                Exit For
            End If
        Next Index28
        
        session.FindById("wnd[0]").SendVKey 0    'Enter

    Next Index
    
    On Error GoTo PressEnter
    
    session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT").VerticalScrollbar.Position = 0
    session.FindById("wnd[0]/tbar[0]/btn[11]").Press 'Save
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press 'Back
    
    BOM_Creation.Activate
    
    If Left(GetObject("SAPGUI").GetScriptingEngine.Children(0).Children(SAPIndex + 0).FindById("wnd[0]").Text, 15) = "SAP Easy Access" Then
        MsgBox "B.O.M. " & BOM_V_Number & " has been created", Title:="Process Completed!"
    Else
        MsgBox "Process Failed! Check SAP for the issue.", Title:="Error: Failed to Create B.O.M."
    End If
        
    BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True

    Exit Sub
    
    'Bulk items/ect press enter
PressEnter:
    EndlessLoopCounter = EndlessLoopCounter + 1
    
    If Left(GetObject("SAPGUI").GetScriptingEngine.Children(0).Children(SAPIndex + 0).FindById("wnd[0]").Text, 35) = "Create material BOM: Initial Screen" Then 'B.O.M. already exists
        session.FindById("wnd[0]/tbar[0]/btn[3]").Press
        MsgBox "B.O.M. " & BOM_V_Number & " already exists in SAP or is not active", Title:="Error: Failed to Create B.O.M."
        BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        Exit Sub
    End If
    
    If EndlessLoopCounter > 60 Then
    
        Dim EmailApp As Outlook.Application: Set EmailApp = New Outlook.Application
        Dim EmailItem As Outlook.MailItem: Set EmailItem = EmailApp.CreateItem(olMailItem)
        Dim ErrorVar As String: ErrorVar = Err.Number & " - " & Err.Source & " - " & Err.Description & " - " & Err.LastDllError & " - " & Err.HelpContext
        
        With EmailItem
            .To = "j.purdon@schenckprocess.com"
            .Subject = "SAP ERROR"
            .Body = ErrorVar
            .Send
        End With
        
        MsgBox "Process got caught in an endless loop. Check SAP for the issue.", Title:="Error: Failed to Create B.O.M."
        
        BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
        Exit Sub
        
    End If
    session.FindById("wnd[0]").SendVKey 0        'Enter
    Resume
    
End Sub

'Find the available SAP BOM rows
Function FindSapMaxBomRow(SAP_Session As GuiSession) As Long

    FindSapMaxBomRow = SAP_Session.FindById("wnd[0]/" & T_CS02_Table).VisibleRowCount
    
End Function

Sub FilterBOM()
    'Clear Old Info
    ProcessDataBOM.Range("B7:E506").ClearContents

    'Set up clean B.O.M.
    FI2 = 7
    For FI1 = 7 To 506
        If BOM_Creation.Cells(FI1, 3).Value <> "" Then
            ProcessDataBOM.Cells(FI2, 2).Value = BOM_Creation.Cells(FI1, 2).Value
            If UCase(BOM_Creation.Cells(FI1, 6).Value) <> "TEXT" Then
                ProcessDataBOM.Cells(FI2, 3).Value = ProcessDataBOM.Cells(FI1, 10).Value
            Else
                ProcessDataBOM.Cells(FI2, 3).Value = BOM_Creation.Cells(FI1, 3).Value
            End If
            ProcessDataBOM.Cells(FI2, 4).Value = BOM_Creation.Cells(FI1, 5).Value
            ProcessDataBOM.Cells(FI2, 5).Value = BOM_Creation.Cells(FI1, 6).Value
            FI2 = FI2 + 1
        End If
    Next FI1
    BOM_Items = ProcessDataBOM.Cells(5, 4).Value
       
    'Sort By Balloon Number
    ProcessDataBOM.Activate
    Range("B7:B506").Select
    ProcessDataBOM.Sort.SortFields.Clear
    ProcessDataBOM.Sort.SortFields.Add Key:=Range("B7") _
        , SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
        
    With ProcessDataBOM.Sort
        .SetRange Range("B7:E506")
        .Header = xlNo
        .MatchCase = False
        .Orientation = xlTopToBottom
        .SortMethod = xlPinYin
        .Apply
    End With
    
    BOM_Creation.Activate
    
End Sub

Sub ClearBOM()
    'Clear B.O.M. table
    BOM_Creation.Protect Contents:=False
    ProcessDataBOM.Protect Contents:=False
    
    BOM_Creation.Cells(4, 3).Value = ""
    BOM_Creation.Cells(4, 10).Value = "No"
    
    BOM_Creation.Range("B7:C506").ClearContents
    BOM_Creation.Range("E7:F506").ClearContents
    BOM_Creation.Range("Z7:AA506").ClearContents
    
    ProcessDataBOM.Range("B7:E506").ClearContents
    ProcessDataBOM.Range("L7:N506").ClearContents
    
    BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
End Sub

Sub BOMtoFileImport()

    Dim Material_Regex As RegExp: Set Material_Regex = New RegExp
    
    Material_Regex.Pattern = "[vVwW]\d{6}\.?[aAbB]\d{2}"
    
    Application.DisplayAlerts = False
    Application.ScreenUpdating = False
    
    BOM_Creation.Protect Contents:=False
    ProcessDataBOM.Protect Contents:=False
    
    ImportFile = Application.GetOpenFilename(Title:="Please choose a file to open", FileFilter:="Excel Files *.xls* (*.xls*),")
    
    If UCase(Left(ImportFile, 5)) <> "FALSE" Then
        
        BOM_Creation.Range("B7:C506").ClearContents
        BOM_Creation.Range("E7:E506").ClearContents
        BOM_Creation.Range("Z7:AA506").ClearContents
        
        ProcessDataBOM.Range("B7:D506").ClearContents
        
        'Dim ImportWorkbook As Workbook: Set ImportWorkbook = Application.ActiveWorkbook
        Dim ImportWorkbook As Workbook: Set ImportWorkbook = Workbooks.Open(Filename:=ImportFile)
        Dim ImportWorksheet As Worksheet: Set ImportWorksheet = ImportWorkbook.ActiveSheet
        Dim workbookName As String: workbookName = ImportWorkbook.Name
        
        If Material_Regex.Test(workbookName) Then
        
            Set matNumCollection = Material_Regex.Execute(workbookName)
            If matNumCollection.Count = 1 Then BOM_Creation.Range("C4") = matNumCollection.Item(0)
            
        End If
        
        If (ImportWorksheet.Range("A1").Value = "PART LIST") Then
        
            Dim LastColumn As Long
            LastColumn = ImportWorksheet.Cells.Find("*", SearchOrder:=xlByColumns, SearchDirection:=xlPrevious).Column
            
            Dim CurrentColumn As Long
            
            For CurrentColumn = 1 To LastColumn
            
                Select Case Trim(UCase(ImportWorksheet.Cells(2, CurrentColumn).Value))
                Case "ITEM"
                    With ImportWorksheet
                        .Range(.Cells(3, CurrentColumn), .Cells(502, CurrentColumn)).Copy
                    End With
                    BOM_Creation.Range("B7:B506").PasteSpecial Paste:=xlPasteValues
                Case "QTY."
                    With ImportWorksheet
                        .Range(.Cells(3, CurrentColumn), .Cells(502, CurrentColumn)).Copy
                    End With
                    BOM_Creation.Range("E7:E506").PasteSpecial Paste:=xlPasteValues
                Case "PART NUMBER"
                    With ImportWorksheet
                        .Range(.Cells(3, CurrentColumn), .Cells(502, CurrentColumn)).Copy
                    End With
                    BOM_Creation.Range("C7:C506").PasteSpecial Paste:=xlPasteValues
                Case "MATL NUMBER"
                    With ImportWorksheet
                        .Range(.Cells(3, CurrentColumn), .Cells(502, CurrentColumn)).Copy
                    End With
                    BOM_Creation.Range("Z7:Z506").PasteSpecial Paste:=xlPasteValues
                Case "MATLQTY"
                    With ImportWorksheet
                        .Range(.Cells(3, CurrentColumn), .Cells(502, CurrentColumn)).Copy
                    End With
                    BOM_Creation.Range("AA7:AA506").PasteSpecial Paste:=xlPasteValues
                End Select
                
            Next

        Else
        
            ImportWorksheet.Range("A2:A501").Copy
            BOM_Creation.Range("B7:B506").PasteSpecial Paste:=xlPasteValues
            
            ImportWorksheet.Range("D2:D501").Copy
            BOM_Creation.Range("C7:C506").PasteSpecial Paste:=xlPasteValues
            
            ImportWorksheet.Range("B2:B501").Copy
            BOM_Creation.Range("E7:E506").PasteSpecial Paste:=xlPasteValues
        
        End If
        
        ImportWorkbook.Close
        
        BOM_Creation.Activate
        BOM_Creation.Range("C4").Select
        
    End If
    
    checkMats
    
    BOM_Creation.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    ProcessDataBOM.Protect DrawingObjects:=True, Contents:=True, Scenarios:=True, AllowFiltering:=True
    
    Application.DisplayAlerts = True
    Application.ScreenUpdating = True
    
End Sub

'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
'                                REVISIT THIS - MIGHT NOT BE RELEVANT
'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
'!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! TODO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Sub SAP_CS02()
    CS02_Flag = True

    session.FindById("wnd[0]").maximize
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nCS02"
    session.FindById("wnd[0]").SendVKey (0)
    session.FindById("wnd[0]/usr/ctxtRC29N-MATNR").Text = BOM_V_Number
    session.FindById("wnd[0]/usr/ctxtRC29N-WERKS").Text = "1111"
    session.FindById("wnd[0]/usr/ctxtRC29N-STLAN").Text = "1"
    session.FindById("wnd[0]").SendVKey 0
    
    Dim BOM_Table As GuiTableControl: Set BOM_Table = session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT")
    Dim Column_Count As Long: Column_Count = BOM_Table.Columns.Count
    Dim Row_Count As Long: Row_Count = BOM_Table.RowCount
    Dim Visible_Row_Count As Long: Visible_Row_Count = BOM_Table.VisibleRowCount
    Dim Current_Column_Index As Long
    Dim Current_Absolute_Row_Index As Long
    Dim Current_Row_Index As Long
    Dim Item_Column_Index As Long
    Dim Component_Item_Index As Long
    Dim Quantity_Item_Index As Long
    
    For Current_Column_Index = 0 To Column_Count - 1
        
        Select Case BOM_Table.Columns.Item(Current_Column_Index).Title
        Case "Item"
            Item_Column_Index = Current_Column_Index
        Case "Component"
            Component_Item_Index = Current_Column_Index
        Case "Quantity"
            Quantity_Item_Index = Current_Column_Index
        End Select
    Next
    
    Current_Absolute_Row_Index = 0
    
    Dim Current_Row As GuiTableRow
    Dim Remaining_Rows As Long: Remaining_Rows = Row_Count
    
    ProcessDataBOM.Range("L7:N506").ClearContents
    
Next_Screen:

    On Error GoTo InvalidCell
    
    Set BOM_Table = session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT")
    
    For Current_Row_Index = 0 To Visible_Row_Count - 1
    
        Current_Absolute_Row_Index = Current_Absolute_Row_Index + 1
        'PUT A FORK IN IT
        ProcessDataBOM.Cells.Item(Current_Absolute_Row_Index + 6, 12) = BOM_Table.GetCell(Current_Row_Index, Item_Column_Index).Text
        ProcessDataBOM.Cells.Item(Current_Absolute_Row_Index + 6, 13) = BOM_Table.GetCell(Current_Row_Index, Component_Item_Index).Text
        ProcessDataBOM.Cells.Item(Current_Absolute_Row_Index + 6, 14) = BOM_Table.GetCell(Current_Row_Index, Quantity_Item_Index).Text
        
    Next
    
    Remaining_Rows = Remaining_Rows - Visible_Row_Count
    
    If Remaining_Rows >= Visible_Row_Count Then
        
        BOM_Table.VerticalScrollbar.Position = BOM_Table.VerticalScrollbar.Position + Visible_Row_Count
        GoTo Next_Screen
        
    End If
    
InvalidCell:

    Set BOM_Table = session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT")
    BOM_Table.VerticalScrollbar.Position = 0
    Set BOM_Table = session.FindById("wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT")

    session.FindById("wnd[0]").SendVKey (27)
    session.FindById("wnd[0]").SendVKey (14)
    session.FindById("wnd[1]/usr/btnSPOP-OPTION1").Press
    
End Sub

Sub Verify_Routing_Status(Optional ByVal Reporting_Option As String = "0", _
                          Optional ByVal Reporting_Location As String = "C:\")
    
    ProcessRoutingBOM.Protect DrawingObjects:=False, Contents:=False, Scenarios:=False, AllowSorting:=True, AllowFiltering:=True
    Dim Report_Required As Boolean: Report_Required = False
    
    If [BOM_Creation_Material_Number] = vbNullString Then
        MsgBox "No material number entered." & vbNewLine & "Enter a material number in cell C4 before checking routing.", vbInformation, "No Material Number"
        Exit Sub
    End If

    ProcessRoutingBOM.Range("C8:E507").ClearContents
    ProcessRoutingBOM.Range("G8:G507").ClearContents
    
    'Check if logged on and initiate the connection
    On Error GoTo SAP_NotLoggedIn
    Dim SAP_GUI As Object: Set SAP_GUI = GetObject("SAPGUI")
    Dim SAP_App As GuiApplication: Set SAP_App = SAP_GUI.GetScriptingEngine
    Dim SAP_Connection As GuiConnection: Set SAP_Connection = SAP_App.Connections(0)
    On Error GoTo 0
    
StartLookingForEasyAccess:
    'Find Number of instances (children) open
    Dim SAP_Session As GuiSession
    Dim NumOfWindowsSAP As Long: NumOfWindowsSAP = SAP_Connection.Sessions.Count
    Dim SAPIndex As Long

    'Seach for an initial "SAP Easy Access" Screen
    For SAPIndex = 0 To NumOfWindowsSAP - 1
        If Left(SAP_Connection.Children(CInt(SAPIndex)).FindById("wnd[0]").Text, 15) = "SAP Easy Access" Then
            Set SAP_Session = SAP_Connection.Children(CInt(SAPIndex))
            Exit For
        End If
    Next SAPIndex
     
    'If a session is not established (None of the instances are "SAP Easy Access")
    If SAP_Session Is Nothing Then
        'If a new instance can be open
        If NumOfWindowsSAP < 6 Then
            SAP_Connection.Sessions.Item(0).CreateSession
            While NumOfWindowsSAP = SAP_Connection.Sessions.Count
            Wend
            GoTo StartLookingForEasyAccess
            'At max instances, cause an error
        Else
            MsgBox "Cannot connect to SAP. Open an ""SAP Easy Access"" window to run the program.", Title:="Error!"
            Exit Sub
        End If
    End If

    Dim SAP_Window As GuiMainWindow: Set SAP_Window = SAP_Session.FindById("wnd[0]")

    SAP_Session.StartTransaction ("CS13")
    SAP_Window.FindById("usr/ctxtRC29L-MATNR").Text = [BOM_Creation_Material_Number]
    SAP_Window.FindById("tbar[1]/btn[8]").Press
    
    Dim BOM_Grid_View As GuiGridView: Set BOM_Grid_View = SAP_Window.FindById("usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
    Dim Grid_View_Row_Count As Long: Grid_View_Row_Count = BOM_Grid_View.RowCount
    Dim Grid_View_Visible_Rows As Long: Grid_View_Visible_Rows = BOM_Grid_View.VisibleRowCount
    
    For i = 0 To Grid_View_Row_Count - 1
        ProcessRoutingBOM.Cells(i + 8, 3).Value = BOM_Grid_View.GetCellValue(i, "DOBJT")
        If (i Mod Grid_View_Row_Count) Then
            
            BOM_Grid_View.FirstVisibleRow = i
        
        End If
    Next

    For i = 1 To Grid_View_Row_Count
        
        If (ProcessRoutingBOM.Cells(i + 7, 6).Text = "#N/A") Or Not (Left(ProcessRoutingBOM.Cells(i + 7, 3), 1) = "W") Then
            GoTo NextLine
        End If
        
        SAP_Session.StartTransaction ("ZJ61")
        
        SAP_Window.FindById("usr/ctxtMARA-MATNR").Text = ProcessRoutingBOM.Cells(i + 7, 3).Value
        SAP_Window.SendVKey (6)
        
        ProcessRoutingBOM.Cells(i + 7, 4).Value = SAP_Window.FindById("usr/ctxtZJ61_D1100-DISPO").Text
        ProcessRoutingBOM.Cells(i + 7, 7).Value = SAP_Window.FindById("usr/ctxtZJ61_D1100-SOBSL").Text
        
NextLine:
        
    Next

    For i = 1 To Grid_View_Row_Count
    
        If ProcessRoutingBOM.Cells(i + 7, 4).Value = "11B" And ProcessRoutingBOM.Cells(i + 7, 7).Value <> "50" Then
            
            SAP_Session.StartTransaction ("CA03")
            
            SAP_Window.FindById("usr/ctxtRC27M-MATNR").Text = ProcessRoutingBOM.Cells(i + 7, 3).Value
            SAP_Window.SendVKey (7)
            
            If SAP_Session.Children.Count > 1 Then
                Report_Required = True

                ProcessRoutingBOM.Cells(i + 7, 5).Value = "NO ROUTING"
                SAP_Session.FindById("wnd[1]/usr/btnCANCEL").Press
            Else
                ProcessRoutingBOM.Cells(i + 7, 5).Value = "ROUTING"
            End If
        End If
    Next

    SAP_Window.SendVKey (15)

    If Report_Required Then
        
        Select Case Reporting_Option
        Case "0"
            Routing_Email_Option
        Case "1", "2"
            Routing_Report_Option (Reporting_Location)
        Case Else
            Debug.Print
        End Select
        
        MsgBox "Additional Routing Required: Report Generated", vbInformation
    Else
        MsgBox "No Additional Routing Required", vbInformation
    End If
    
    End
SAP_NotLoggedIn:
    MsgBox "Please sign into SAP to continue", Title:="Error!"
    End
    
End Sub

Sub Routing_Email_Option()

    Dim Email_Text As String: Email_Text = "<!DOCTYPE html><html><head><style>table{border-collapse:collapse;}" & _
        "tr{border-bottom:1px solid #ddd;}th{padding-right:1em;}</style></head>" & _
        "<body><table><tr><th>MATERIAL NUMBER</th><th>MRP CONTROLLER</th>" & _
        "<th>DESCRIPTION</th></tr>"
        
    Dim Routing_Index As Long
    For Routing_Index = 8 To ProcessRoutingBOM.Cells(ProcessRoutingBOM.Rows.Count, "C").End(xlUp).Row
    
        If ProcessRoutingBOM.Cells(Routing_Index, "E") = "NO ROUTING" Then
        
            Dim TableRow As String: TableRow = "<tr><td>" & ProcessRoutingBOM.Cells(i + 7, 3) & _
                                                                                              "</td><td>" & ProcessRoutingBOM.Cells(i + 7, 4) & "</td><td>" & _
                                                                                              ProcessRoutingBOM.Cells(i + 7, 6) & "</td></tr>"
            Email_Text = Email_Text & TableRow
        End If
    
    Next Routing_Index
                                        
    Email_Text = Email_Text & "</table></body></html>"
    
    Dim EmailApp As Outlook.Application: Set EmailApp = New Outlook.Application
    Dim EmailItem As Outlook.MailItem: Set EmailItem = EmailApp.CreateItem(olMailItem)
    
    With EmailItem
        .To = Environ("Username") & "@schenckprocess.com"
        .Subject = "BOM ROUTING REPORT: " & BOM_Creation.Range("C4")
        .HTMLBody = Email_Text
        .Send
    End With


End Sub

Sub Routing_Report_Option(ByVal Reporting_Location As String)

    Dim Routing_Report_WB As Workbook: Set Routing_Report_WB = Workbooks.Add
    Dim Routing_Report_WS As Worksheet: Set Routing_Report_WS = Routing_Report_WB.ActiveSheet
    
    Dim Report_Name As String: Report_Name = BOM_Creation.Range("C4").Text & " - Routing Report.xlsx"
    Dim Report_Location As String: Report_Location = Reporting_Location
    Dim Routing_WS_Current_Index As Long: Routing_WS_Current_Index = 2
    
    
    With Routing_Report_WS
    
        .Range("A1").Value = "MATERIAL NUMBER"
        .Range("B1").Value = "MRP CONTROLLER"
        .Range("C1").Value = "DESCRIPTION"
        
        Dim Routing_Index As Long
        For Routing_Index = 8 To ProcessRoutingBOM.Cells(ProcessRoutingBOM.Rows.Count, "C").End(xlUp).Row
            If ProcessRoutingBOM.Cells(Routing_Index, "E").Value = "NO ROUTING" Then

                .Cells(Routing_WS_Current_Index, "A").Value = ProcessRoutingBOM.Cells(Routing_Index, "C").Value
                .Cells(Routing_WS_Current_Index, "B").Value = ProcessRoutingBOM.Cells(Routing_Index, "D").Value
                .Cells(Routing_WS_Current_Index, "C").Value = ProcessRoutingBOM.Cells(Routing_Index, "F").Value
                Routing_WS_Current_Index = Routing_WS_Current_Index + 1
            
            End If
        Next Routing_Index
        
        .Range("A1:C100").Borders.LineStyle = xlContinuous
        .Range("A1:C100").Columns.AutoFit
    
    End With
    
    Routing_Report_WB.SaveAs Reporting_Location & "\" & Report_Name, xlWorkbookDefault
    Routing_Report_WB.Close

End Sub

Function getLastRow(ByRef worksheetName As String, ByVal columnInput As String) As Long

    getLastRow = ThisWorkbook.Worksheets(worksheetName).Cells(ThisWorkbook.Worksheets(worksheetName).Rows.Count, columnInput).End(xlUp).Row

End Function

Sub checkMats()

    ThisWorkbook.Protect Structure:=False, Windows:=False
    
    refreshMaterialBOMsTable
    
    BOM_Dump.Range("F2:H10000").ClearContents
    'Get Last Rows, set duplicate
    Dim BOM_CreationLastRow As Long: BOM_CreationLastRow = getLastRow("BOM_Creation", "C")
    Dim BOM_DumpLastRow As Long: BOM_DumpLastRow = getLastRow("BOM_Dump", "B") + 1
    Dim BOM_DumpDuplicateRow As Long: BOM_DumpDuplicateRow = 2
    
    'Dim iterators
    Dim partNumberIterator As Long
    Dim materialNumberIterator As Long
    
    'db and rs
    Dim oConnection As ADODB.Connection: Set oConnection = New ADODB.Connection
    Dim oRecordSet As ADODB.Recordset: Set oRecordSet = New ADODB.Recordset
    
    oConnection.ConnectionString = databaseConnectionString
    oConnection.Open
    oRecordSet.ActiveConnection = oConnection
    
    For partNumberIterator = 7 To BOM_CreationLastRow
    
        Dim currentMaterial As String: currentMaterial = BOM_Creation.Cells(partNumberIterator, "C").Value
        Dim currentMatBOM As String: currentMatBOM = BOM_Creation.Cells(partNumberIterator, "Z").Value
        Dim currentMatQty As String: currentMatQty = BOM_Creation.Cells(partNumberIterator, "AA").Value
        
        Dim recordSetSource As String: recordSetSource = "INSERT INTO WW_Material_BOMs (PartNumber, MaterialNumber, MaterialQuantity) VALUES ('" _
          & currentMaterial & "','" & currentMatBOM & "','" & currentMatQty & "')"

        If Not currentMatBOM = vbNullString And Not currentMaterial = "-" And _
            Not currentMatQty = vbNullString And Not currentMatQty = "-" And _
            Not currentMatQty = "0" Then
            
            For materialNumberIterator = 2 To BOM_DumpLastRow
                
                If BOM_Dump.Cells(materialNumberIterator, "B").Value = currentMaterial Then GoTo NextOne
                
            Next materialNumberIterator
            
            oRecordSet.Source = recordSetSource
            oRecordSet.Open
            
            refreshMaterialBOMsTable
            
            BOM_Dump.Cells(BOM_DumpDuplicateRow, "F") = currentMaterial
            BOM_Dump.Cells(BOM_DumpDuplicateRow, "G") = currentMatBOM
            BOM_Dump.Cells(BOM_DumpDuplicateRow, "H") = currentMatQty
            
            'BOM_DumpLastRow = BOM_DumpLastRow + 1
            BOM_DumpDuplicateRow = BOM_DumpDuplicateRow + 1

        End If
NextOne:
        'Stop
    Next partNumberIterator
    
    If BOM_Dump.Range("F2").Value <> vbNullString Then createResultsWB
    
    ThisWorkbook.Protect Structure:=True, Windows:=False
    
End Sub


Sub createResultsWB()
    Dim templateName As String: templateName = "BulkBOMs.xltm"
    Dim templateLocation As String: templateLocation = "\\USWWQ-P-FS01.cps.local\orders\Common Files\CPE_Schedule\" & templateName

    Dim matResultsWB As Workbook: Set matResultsWB = Workbooks.Open(templateLocation)
    Dim matResultsWS As Worksheet: Set matResultsWS = matResultsWB.ActiveSheet
    
    Dim lastRow As Long: lastRow = getLastRow("BOM_Dump", "F")
    BOM_Dump.Range("F2:H" & lastRow).Copy
    
    matResultsWS.Range("A2:C" & lastRow).PasteSpecial Paste:=xlPasteValues
    
    Dim userProfile As String: userProfile = Environ$("USERPROFILE")
    Dim matResultsName As String: matResultsName = Timer & "_Bulk BOM.xlsm"
    Dim matResultsFullName As String: matResultsFullName = userProfile & "\Documents\" & matResultsName
    
    matResultsWB.SaveAs matResultsFullName, FileFormat:=xlOpenXMLWorkbookMacroEnabled
    
    MsgBox ("Some parts require 'Material BOMs'" & vbNewLine & "File Saved: " & matResultsFullName)
    
End Sub


Sub refreshMaterialBOMsTable()

    Dim materialBOMsConnection As OLEDBConnection: Set materialBOMsConnection = ThisWorkbook.Connections("Query - WW_Material_BOMs").OLEDBConnection
    
    ThisWorkbook.Protect Structure:=False, Windows:=False
    
    materialBOMsConnection.BackgroundQuery = False
    materialBOMsConnection.Refresh
    materialBOMsConnection.BackgroundQuery = True

End Sub

Sub function_test()

    Dim somestr As String: somestr = "S-V305688.B01,W-" & vbNewLine & "V154190.B01"
    Dim anotherstr As String
    
    anotherstr = format_material_number(somestr)


End Sub


Function format_material_number(ByVal material As String) As String

    Dim formatted_material As String
    formatted_material = Trim$(material)
    
    If InStr(1, ",", formatted_material) Then
        
        Dim temp_num As Long
        temp_num = InStr(1, ",", formatted_material)
        
        Stop
    
    End If
    
    

End Function

