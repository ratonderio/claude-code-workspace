Attribute VB_Name = "Module4_AddInfoRecords"
'@Folder "Modules"
Sub Sequence_AddInfoRecord()
    File_Name = Application.ThisWorkbook.Name
    UserName = UCase(Environ("Username"))
    lastRow = 0
    InfoRecordCreatedForStr = "Info Records Were Created for Parts:" + vbCr
    
    'Find Boundry
    For Index = 5 To 103
        If ProcessDataCPN.Cells(Index, 13).Value = "Good" Then
            lastRow = Index
        Else
            Exit For
        End If
    Next Index
    
    'If OK to Proceed
    If lastRow = 0 Then
        Exit Sub
    End If
    
    Call InitiateSAP
        
    For Index = 5 To lastRow
        V_Number = UCase(CreatePartNumbers.Cells(Index, 3).Value)
        ProjNum = CreatePartNumbers.Cells(Index, 4).Value
        C_Number = UCase(CreatePartNumbers.Cells(Index, 5).Value)
        InfoRecordRev = UCase(CreatePartNumbers.Cells(Index, 6).Value)
        V_NumDesc = CreatePartNumbers.Cells(Index, 7).Value
        StoreLoc = CreatePartNumbers.Cells(Index, 10).Value
        ProdHier = CreatePartNumbers.Cells(Index, 11).Value
        
        Call SAP_CV01N
        Call SAP_MM02_AddInfoRecord
        
        InfoRecordCreatedForStr = InfoRecordCreatedForStr & V_Number & ", "

        Call StoreInDatabase
        Call UpdateMaterials
    Next Index
    
    Application.ScreenUpdating = False
    Call ReadFromDatabase
    Application.ScreenUpdating = True
    CreatePartNumbers.Activate
    
    InfoRecordCreatedForStr = Left(InfoRecordCreatedForStr, Len(InfoRecordCreatedForStr) - 2)
    MsgBox InfoRecordCreatedForStr, Title:="Info Records Created"

End Sub

Sub SAP_MM02_AddInfoRecord()
    
    session.FindById("wnd[0]").maximize
    
    'Enter info
    session.FindById("wnd[0]/tbar[0]/okcd").Text = "MM02"
    session.FindById("wnd[0]").SendVKey 0
    session.FindById("wnd[0]/usr/ctxtRMMG1-MATNR").Text = V_Number
    session.FindById("wnd[0]/tbar[1]/btn[5]").Press 'Select Screens
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(0).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(3).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(6).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(9).Selected = True
    session.FindById("wnd[1]/usr/tblSAPLMGMMTC_VIEW").GetAbsoluteRow(11).Selected = True
    session.FindById("wnd[1]/tbar[0]/btn[6]").Press 'Set Org Settings
    session.FindById("wnd[1]/usr/ctxtRMMG1-WERKS").Text = "1111"
    session.FindById("wnd[1]/usr/ctxtRMMG1-LGORT").Text = "" 'StorageCode
    session.FindById("wnd[1]/usr/ctxtRMMG1-VKORG").Text = "1140"
    session.FindById("wnd[1]/usr/ctxtRMMG1-VTWEG").Text = "VK"
    session.FindById("wnd[1]/tbar[0]/btn[0]").Press
    
    'Assign Info Record
    session.FindById("wnd[0]/tbar[1]/btn[27]").Press
    session.FindById("wnd[1]/usr/subSCREEN:SAPLCV140:0204/tblSAPLCV140SUB_DOC/ctxtDRAW-DOKAR[0,0]").Text = "GRP"
    session.FindById("wnd[1]/usr/subSCREEN:SAPLCV140:0204/tblSAPLCV140SUB_DOC/ctxtDRAW-DOKNR[1,0]").Text = V_Number
    session.FindById("wnd[1]").SendVKey 0
    session.FindById("wnd[1]/tbar[0]/btn[8]").Press
    
    'Change the Description
    session.FindById("wnd[0]/usr/subSUB1:SAPLMGD1:1002/txtMAKT-MAKTX").Text = V_NumDesc
    MFG_Info = session.FindById("wnd[0]/usr/subSUB6:SAPLZZ_MGD1:0001/txtMARA-ZZ_TEILENUMMER").Text
    
    'Find Info
    Call FindStorLoc
    Call FindHierarchy

    'Exit
    session.FindById("wnd[0]/tbar[0]/btn[11]").Press
    session.FindById("wnd[0]/tbar[0]/btn[3]").Press
End Sub

Sub FindStorLoc()
    'GoTo MRP2
    session.FindById("wnd[0]/mbar/menu[2]/menu[12]").Select
    'Find Made vs Buy
    If session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2484/ctxtMARC-BESKZ").Text = "E" Then
        PartType = "Make To Order (Ind)"
    ElseIf session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2484/ctxtMARC-BESKZ").Text = "F" Then
        PartType = "Purchased To Order (Ind)"
    Else
        PartType = ""
    End If
    'Find Storage Location
    StorageCode = session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2484/ctxtMARC-LGPRO").Text
    StoreLoc = ""
    LastRowWorking = Dropdowns.Cells(Rows.Count, 2).End(xlUp).Row
    For IndexWorking = 3 To LastRowWorking
        If Left(Right(Dropdowns.Cells(IndexWorking, 2).Value, 5), 4) = StorageCode Then
            StoreLoc = Dropdowns.Cells(IndexWorking, 2).Value
            Exit For
        End If
    Next IndexWorking
End Sub

Sub FindHierarchy()
    'GoTo Sales: Sales Org Data 2
    session.FindById("wnd[0]/mbar/menu[2]/menu[4]").Select
    'Find Product Hierarchy
    If ProdHier = "" Then
        ProdHierCode = session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2157/ctxtMVKE-PRODH").Text
        LastRowWorking = Dropdowns.Cells(Rows.Count, 9).End(xlUp).Row
        For IndexWorking = 3 To LastRowWorking
            If UCase(Dropdowns.Cells(IndexWorking, 9).Value) = UCase(ProdHierCode) Then
                ProdHier = Dropdowns.Cells(IndexWorking, 8).Value
                Exit For
            End If
        Next IndexWorking
    Else
        'Set the Product Hierarchy Code
        LastRowWorking = Dropdowns.Cells(Rows.Count, 8).End(xlUp).Row
        ProdHierCode = ""
        For IndexHier = 3 To lastRow
            If UCase(ProdHier) = UCase(Dropdowns.Cells(IndexHier, 8).Value) Then
                ProdHierCode = Dropdowns.Cells(IndexHier, 9).Value
                Exit For
            End If
        Next IndexHier
        session.FindById("wnd[0]/usr/subSUB2:SAPLMGD1:2157/ctxtMVKE-PRODH").Text = ProdHierCode
    End If
End Sub
