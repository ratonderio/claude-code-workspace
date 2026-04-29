Attribute VB_Name = "Module5_OFF2"
'@Folder("Modules")

Sub asd()

    Dim oSAP As SAP_Object: Set oSAP = New SAP_Object
    Dim sapSession As GuiSession: Set sapSession = oSAP.SAP_Session
    Dim sapMainWindow As GuiMainWindow: Set sapMainWindow = oSAP.SAP_MainWindow
    
    sapSession.StartTransaction "CS13"
    
    sapMainWindow.FindById("usr/ctxtRC29L-MATNR").Text = "V608689.B03"
    sapMainWindow.SendVKey (V_F8)
    
    Dim sapGrid As GuiGridView: Set sapGrid = sapMainWindow.FindById("usr/cntlGRID1/shellcont/shell/shellcont[1]/shell")
    'Dim componentNumberColumn As Long: test = sapGrid.GetColumnPosition("DOBJT")
    Dim currentRow As Long
    
    ProcessRoutingBOM.Range("M6:M200").ClearContents
    For currentRow = 0 To sapGrid.RowCount - 1
        ProcessRoutingBOM.Cells(currentRow + 6, "M").Value = sapGrid.GetCellValue(currentRow, "DOBJT")
    Next currentRow
    
    Stop

End Sub

Sub dfg()

    Dim dbConnection As ADODB.Connection: Set dbConnection = New ADODB.Connection
    Dim dbRecordset As ADODB.Recordset: Set dbRecordset = New ADODB.Recordset
    
    dbConnection.ConnectionString = databaseConnectionString
    dbConnection.Open
    
    dbRecordset.ActiveConnection = dbConnection
    
    Dim anIter As Long
    Dim queryString As String
    Dim currentCell As String
    
    For anIter = 6 To 41
        currentCell = ProcessRoutingBOM.Cells(anIter, "M")
        queryString = "SELECT * FROM SAP_Tool_History WHERE V_Num = '" & currentCell & "'"
        dbRecordset.Source = queryString
        dbRecordset.Open
        
        If Not dbRecordset.EOF Then
            Debug.Print "RECORD FOUND"
        Else
            dbRecordset.Close
            queryString = "INSERT INTO SAP_Tool_History VALUES (newid(), '" & Now & "', 'OFF2', '" & currentCell & "', '', '', '', '', '', '', '', 'Y') "
            dbRecordset.Source = queryString
            
            Debug.Print queryString
            
            dbRecordset.Open
            
        End If
        
        If dbRecordset.State = adStateOpen Then dbRecordset.Close
    
    Next anIter
    
    Stop
End Sub


Sub importWorkbooks()

    Dim folderString As String: folderString = Environ("USERPROFILE") & "\Documents\BulkBOMs\"
    
End Sub


Sub LoopThroughFiles()

Dim oFSO As Object
Dim oFolder As Object
Dim oFile As Object
Dim i As Integer

Dim folderString As String: folderString = Environ("USERPROFILE") & "\Documents\BulkBOMs\"

Set oFSO = CreateObject("Scripting.FileSystemObject")

Set oFolder = oFSO.GetFolder(folderString)

For Each oFile In oFolder.Files

    Debug.Print oFile.Name
    
    i = i + 1

Next oFile

End Sub
