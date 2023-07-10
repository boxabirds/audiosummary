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

{#if currentStep === 1}
	{#if processing}
	  <Spinner />
	{:else}
	  <FileUpload {processing} on:upload={event => uploadFile(event.detail.file)} />
	{/if}
{:else if currentStep === 2}
	<SentenceList {processing} {sentences} on:select={event => selectSentences(event.detail.sentences)} />
{:else}
	<AudioPlayer {finalAudio} on:newSummary={newSummary} />
{/if}
