import unreal_engine as ue
import tensorflow as tf
import upythread as ut
import json
import sys
import importlib
import time
import imp

class TensorFlowComponent:

	# constructor adding a component - Unused atm
	#def __init__(self):
	#	ue.log('Component Init')

	# this is called on game start
	def begin_play(self):
		if(self.uobject.VerbosePythonLog):
			ue.log('BeginPlay, importing TF module: ' + self.uobject.TensorFlowModule)

		#import the module
		self.tfModule = importlib.import_module(self.uobject.TensorFlowModule)
		imp.reload(self.tfModule)
		
		#tfc or the class instance holding the pluginAPI
		self.tfapi = self.tfModule.getApi()

		#Valid game world toggle for threading guards
		self.ValidGameWorld = True

		#call our tfapi setup, typically on another thread
		self.setup()

	def end_play(self):
		self.ValidGameWorld = False
		self.tfapi.stop()

	def stop_training(self):
		self.tfapi.stop() 

	#multi-threaded call
	def setup(self, args=None):
		if(self.uobject.ShouldUseMultithreading):
			try:
				if(self.uobject.VerbosePythonLog):
					ue.log('running setup on background thread')
				ut.run_on_bt(self.setup_blocking)
			except:
				e = sys.exc_info()[0]
				ue.log('TensorFlowComponent::setup error: ' + str(e))
		else:
			self.setup_blocking()

	#multi-threaded call
	def train(self, args=None):
		#ensure our training trigger is reset
		self.tfapi.resetTrainingTrigger()

		if(self.uobject.VerbosePythonLog):
			ue.log(self.uobject.TensorFlowModule + ' training scheduled.')

		if(self.uobject.ShouldUseMultithreading):
			try:
				ut.run_on_bt(self.train_blocking)
			except:
				e = sys.exc_info()[0]
				ue.log('TensorFlowComponent::train error: ' + str(e))
		else:
			self.train_blocking()


	#allow call custom functions on the tfapi object. Note all of these are synchronous
	def custom_function(self, args=None):
		#split our custom function call by first ','
		stringList = args.split(',', 1)

		#call our custom function with our passed variables and return result
		return getattr(self.tfapi, stringList[0])(stringList[1])

	#json input
	def json_input(self, args):
		if(self.uobject.VerbosePythonLog):
			ue.log(self.uobject.TensorFlowModule + ' input passed: ' + args)

		#pass the raw json to the script to handle
		resultJson = self.tfapi.runJsonInput(json.loads(args))

		#pass prediction json back
		self.uobject.OnResultsFunction(json.dumps(resultJson))

	#setup blocking
	def setup_blocking(self):

		#call the api setup (may be multi-threaded!)
		self.tfapi.setup()

		#run callbacks only if we're still in a valid game world
		if(self.ValidGameWorld):
			ue.run_on_gt(self.setup_complete)

	#setup callback function
	def setup_complete(self):
		if(self.uobject.VerbosePythonLog):
			ue.log('Setup complete!');

		#train after setup has completed if toggled
		if(self.uobject.ShouldTrainOnBeginPlay):
			self.train()

	#single threaded call
	def train_blocking(self):
		if(self.uobject.VerbosePythonLog):
			ue.log(self.uobject.TensorFlowModule + ' training started on bt thread.')

		#calculate the time it takes to train your network
		start = time.time()
		self.trained = self.tfapi.train()
		stop = time.time()

		if self.trained is None:
			ue.log('Warning! No model object returned from training, running tensorInput will not work. See your train(): method')
			return

		if 'summary' in self.trained:
			summary = self.trained['summary']
		else:
			summary = {}

		summary['elapsed'] = stop-start

		#run callbacks only if we're still in a valid game world
		if(self.ValidGameWorld):
			ue.run_on_gt(self.training_complete, summary)

	#training callback function
	def training_complete(self, summary):
		if(self.uobject.VerbosePythonLog):
			ue.log(self.uobject.TensorFlowModule + ' trained in ' + str(round(summary['elapsed'],2)) + ' seconds.')

		self.uobject.OnTrainingCompleteFunction(json.dumps(summary))