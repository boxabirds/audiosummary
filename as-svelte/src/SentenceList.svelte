<script>
    import { createEventDispatcher } from 'svelte';
    import { Button } from 'svelte-materialify';
  
    export let sentences = [];
    export let processing = false;
  
    const dispatch = createEventDispatcher();
  
    function handleSelectClick() {
      dispatch('select', { sentences });
    }
</script>

{#each sentences as sentence (sentence.id)}
    <div>
      <span>{sentence.text}</span>
      <input type="checkbox" bind:checked="{sentence.selected}" />
    </div>
{/each}
<Button on:click="{handleSelectClick}" disabled="{processing}">Select</Button>
