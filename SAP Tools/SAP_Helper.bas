Attribute VB_Name = "SAP_Helper"
'@Folder "Modules"
'@Folder("VBAProject")
Public Enum V_Keys
    V_Enter = 0
    V_F1 = 1
    V_F2 = 2
    V_Back = 3
    V_F4 = 4
    V_F5 = 5
    V_F6 = 6
    V_F7 = 7
    V_F8 = 8
    V_F9 = 9
    V_F10 = 10
    V_Save = 11
    V_Cancel = 12
    V_Shift_And_F1 = 13
    V_Shift_And_F2 = 14
    V_Exit = 15
    V_Shift_And_F4 = 16
    V_Shift_And_F5 = 17
    V_Shift_And_F6 = 18
    V_Shift_And_F7 = 19
    V_Shift_And_F8 = 20
    V_Shift_And_F9 = 21
    V_Shift_And_Ctrl_And_0 = 22
    V_Shift_And_F11 = 23
    V_Shift_And_F12 = 24
    V_Ctrl_And_F1 = 25
    V_Ctrl_And_F2 = 26
    V_Ctrl_And_F3 = 27 'Select All
    V_Ctrl_And_F4 = 28 'Deselect All
    V_Ctrl_And_F5 = 29
    V_Ctrl_And_F6 = 30
    V_Ctrl_And_F7 = 31
    V_Ctrl_And_F8 = 32
    V_Ctrl_And_F9 = 33
    V_Ctrl_And_F10 = 34
    V_Ctrl_And_F11 = 35
    V_Ctrl_And_F12 = 36
    V_Ctrl_And_Shift_And_F1 = 37
    V_Ctrl_And_Shift_And_F2 = 38
    V_Ctrl_And_Shift_And_F3 = 39
    V_Ctrl_And_Shift_And_F4 = 40
    V_Ctrl_And_Shift_And_F5 = 41
    V_Ctrl_And_Shift_And_F6 = 42
    V_Ctrl_And_Shift_And_F7 = 43
    V_Ctrl_And_Shift_And_F8 = 44
    V_Ctrl_And_Shift_And_F9 = 45
    V_Ctrl_And_Shift_And_F10 = 46
    V_Ctrl_And_Shift_And_F11 = 47
    V_Ctrl_And_Shift_And_F12 = 48
    V_Ctrl_And_E = 70
    V_Ctrl_And_F = 71
    V_Ctrl_And_Forward_Slash = 72
    V_Ctrl_And_Backward_Slash = 73
    V_Ctrl_And_N = 74
    V_Ctrl_And_O = 75
    V_Ctrl_And_X = 76
    V_Ctrl_And_C = 77
    V_Ctrl_And_V = 78
    V_Ctrl_And_Z = 79
    V_First_Page = 80
    V_Previous_Page = 81
    V_Next_Page = 82
    V_Last_Page = 83
    V_Ctrl_And_G = 84
    V_Ctrl_And_R = 85
    V_Ctrl_And_P = 86
End Enum

Public Function Renew_Main_Window(ByRef SAP_Session As GuiSession) As GuiMainWindow

    Set Renew_Main_Window = SAP_Session.FindById("wnd[0]")

End Function

Public Function Renew_Table(ByRef SAP_Session As GuiSession, ByVal SAP_Table_ID As String) As GuiTableControl

    Set Renew_Table = SAP_Session.FindById("wnd[0]/" & SAP_Table_ID)
    
End Function

Public Sub Set_SAP_Table_Position_And_Refresh(ByRef SAP_Session As GuiSession, ByRef SAP_Window As GuiMainWindow, ByRef SAP_Table As GuiTableControl, ByVal SAP_Table_ID As String, ByVal SAP_Scroll_Location As Long)
    
    Set SAP_Window = SAP_Session.FindById("wnd[0]")
    Set SAP_Table = SAP_Window.FindById(SAP_Table_ID)
    
    SAP_Table.VerticalScrollbar.Position = SAP_Scroll_Location
    
    Set SAP_Window = SAP_Session.FindById("wnd[0]")
    Set SAP_Table = SAP_Window.FindById(SAP_Table_ID)

End Sub

Private Sub SAP_Debugger()

    ' SESSION NUMBER IF THERE ARE MULTIPLE SAP LOGON WINDOWS
    Dim Session_Number As Long: Session_Number = 0
    ' TRANSACTION CODE
    Dim Transaction_Number As String: Transaction_Number = ""
    ' ID VALUES
    Dim Find_By_ID_Value_1 As String: Find_By_ID_Value_1 = ""
    Dim Find_By_ID_Value_2 As String: Find_By_ID_Value_2 = ""
    Dim Find_By_ID_Value_3 As String: Find_By_ID_Value_3 = ""
    Dim Find_By_ID_Value_4 As String: Find_By_ID_Value_4 = ""
    Dim Find_By_ID_Value_5 As String: Find_By_ID_Value_5 = ""
    ' TABLE ID
    Dim SAP_Table_ID As String: SAP_Table_ID = "wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT"
    
    Dim SAP_Table As GuiTableControl
    Dim SAP_Table_Rows As GuiComponentCollection
    Dim SAP_Table_Columns As GuiComponentCollection
    
    Dim SAP_GUI As Object: Set SAP_GUI = GetObject("SAPGUI")
    Dim SAP_App As GuiApplication: Set SAP_App = SAP_GUI.GetScriptingEngine
    Dim SAP_Connection As GuiConnection: Set SAP_Connection = SAP_App.Connections(0)
    Dim SAP_Session As GuiSession: Set SAP_Session = SAP_Connection.Sessions(Session_Number)
    Dim SAP_Window As GuiMainWindow: Set SAP_Window = SAP_Session.FindById("wnd[0]")
    
    SAP_Session.StartTransaction (Transaction_Number)
    
    SAP_Window.FindById("usr/ctxtRC29N-MATNR").Text = "W076996.B01"
    SAP_Window.SendVKey (V_F5)
    
    Set SAP_Table = Renew_Table(SAP_Session, SAP_Table_ID)
    
    Set SAP_Table_Rows = SAP_Table.Rows
    Set SAP_Table_Columns = SAP_Table.Columns
    
    Debug.Print "SAP Table Row Count: " & SAP_Table.RowCount
    Debug.Print "SAP Table Visible Row Count: " & SAP_Table.VisibleRowCount
    Debug.Print "SAP Table Valid Row Count: " & SAP_Window.FindByName(F_Table_Valid_Rows, F_Text_Field).Text
    
    'Stop
    
    'Exit Sub

End Sub
