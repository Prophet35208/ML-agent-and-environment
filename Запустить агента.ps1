# ��������� ������� ����������
$OriginalDir = Get-Location

# ��������� � ����� .venv\Scripts
cd .venv\Scripts

# ���������, ���������� �� ���� Activate.ps1
if (Test-Path Activate.ps1) {
    # ���������� ����������� ���������
    . .\Activate.ps1

    # ���������, ������� �� ������������ ���������
    if ($env:VIRTUAL_ENV) {
        Write-Host "����������� ��������� ������������."

        # ������������ � �������� �����
        cd $OriginalDir

        # ���������, ������� �� ��������� � �������� �����
        if ($?) {

            # ��������� agentSimpleRoad.py
            python agentRoad.py

            # ���������, ������� �� ���������� ������
            if ($?) {
            } else {
                Write-Host "������ ��� ������� ������� agentSimpleRoad.py"
            }
        } else {
            Write-Host "������ ��� �������� � �������� ����������."
        }

    } else {
        Write-Host "������: �� ������� ������������ ����������� ���������."
    }
} else {
    Write-Host "������: ���� Activate.ps1 �� ������ � ����� .venv\Scripts. ��������� ���� � ������ ������������ ���������."
}

Read-Host "������� Enter, ����� ����� �� �������"