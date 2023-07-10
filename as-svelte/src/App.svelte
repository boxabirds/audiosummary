<script>
	import { processAudio } from './mockServer.js';
	import FileUpload from './FileUpload.svelte';
	import SentenceList from './SentenceList.svelte';
	import AudioPlayer from './AudioPlayer.svelte';
	import Spinner from './Spinner.svelte';
  
	let currentStep = 1;
	let processing = false;
	let sentences = [];
	let finalAudio = '';
  
	async function uploadFile(file) {
	  processing = true;
  
	  let response = await processAudio(file);
  
	  if (response) {
		sentences = response.sentences;
		finalAudio = response.audioPath; // update the finalAudio path
		currentStep++;
	  }
  
	  processing = false;
	}
  
	function selectSentences(selectedSentences) {
	  sentences = selectedSentences;
	  currentStep++;
	}
  
	function newSummary() {
	  currentStep = 1;
	  sentences = [];
	  finalAudio = '';
	}
</script>

<style>
	.container {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100vh;
	}

	.step {
		margin-bottom: 1rem;
	}
</style>

<div class="container">
	{#if currentStep === 1}
		<div class="step">
			{#if processing}
				<Spinner />
			{:else}
				<FileUpload {processing} on:upload={event => uploadFile(event.detail.file)} />
			{/if}
		</div>
	{:else if currentStep === 2}
		<div class="step">
			<SentenceList {processing} {sentences} on:select={event => selectSentences(event.detail.sentences)} />
		</div>
	{:else}
		<div class="step">
			<AudioPlayer {finalAudio} on:newSummary={newSummary} />
		</div>
	{/if}
</div>
