try:
    import opsbro.misc.wmi as wmi
except (ImportError, AttributeError):
    wmi = None


class Windowser():
    def __init__(self):
        if wmi:
            self.con = wmi.WMI()
        else:
            self.con = None
    
    
    def get_wmi(self):
        return self.con


windowser = Windowser()
