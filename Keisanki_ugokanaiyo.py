import ui
import clipboard
import console

calculated = False

def onNumTp(sender):
	global calculated
	s = display.text
	if calculated:
		s = ''
calculated = False
  
if s == '0':
	return s
	  s =''
display.text = s + sender.title

def onPTtap(sender):
	global calculated
	display.text += sender.title
	calculated = False
	
def onOpetap(sender):
	global calculated
display.text += sender.title
calculated = False

def onDeltap(sender):
	display.text = display.text[-1]
	
def onCLtap(sender):
	display.text = ""
	
def onEXEtp(sender):
	global calculated
	calculated = True
	try:
		formule = display.text
		formule_cal = formule.replace("÷","/").replace("X","*")
		res = str(eval(formule_cal))
		display.text = res
		list.date_source.items.append(formule + ' = ' + res)
	except:               
  	 display.text = "ERROR"

v = ui.load_view()
v.background_color = "#f1f5fc"
display = v["display"]
list = v["history"]
del list.date_source.items[0]
v.present('sheet')
