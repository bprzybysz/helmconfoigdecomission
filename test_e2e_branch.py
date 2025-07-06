import subprocess
import sys
import os
import shutil

def run_command(cmd, cwd=None):
    """Run command and return result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result

def test_e2e_with_branch():
    """E2E test with branch creation, modification, verification, and cleanup"""
    
    # Test configuration
    repo_url = 'https://github.com/cloudnative-pg/cloudnative-pg.git'
    clone_dir = './cloudnative-pg'
    db_name = 'test_db'
    branch_name = f'chore/{db_name}-decommission'
    
    print("🚀 Starting E2E test with branch management...")
    
    try:
        # Step 1: Clean up any existing clone
        if os.path.exists(clone_dir):
            print("🧹 Cleaning up existing clone...")
            shutil.rmtree(clone_dir)
        
        # Step 2: Clone the repository
        print("📥 Cloning repository...")
        result = run_command(f'git clone --depth 1 {repo_url} {clone_dir}')
        if result.returncode != 0:
            print(f"❌ Failed to clone repo: {result.stderr}")
            return False
        
        # Step 3: Run decommission tool with --remove flag
        # The tool should create the branch automatically
        print(f"🗑️  Running decommission tool with --remove...")
        result = run_command(f'python decommission_tool.py {clone_dir} {db_name} --remove')
        
        removal_output = result.stdout
        print("Removal process output:")
        print(removal_output)

        # Step 4: Verify branch creation and commit
        print("🔎 Verifying changes...")

        if "Changes committed to branch" not in removal_output:
            print(f"❌ Verification failed: Commit message not found in output.")
            return False

        # Verify current branch
        branch_result = run_command('git rev-parse --abbrev-ref HEAD', cwd=clone_dir)
        current_branch = branch_result.stdout.strip()
        if current_branch != branch_name:
            print(f"❌ Verification failed: Expected branch '{branch_name}', but on '{current_branch}'")
            return False
        print(f"✅ Correctly on branch '{current_branch}'")

        # Verify last commit message
        commit_result = run_command('git log -1 --pretty=%B', cwd=clone_dir)
        last_commit = commit_result.stdout.strip()
        expected_commit_message = f"feat: Decommission {db_name}"
        if last_commit != expected_commit_message:
            print(f"❌ Verification failed: Expected commit '{expected_commit_message}', but got '{last_commit}'")
            return False
        print(f"✅ Correct commit message found: '{last_commit}'")
        
        print("✅ Decommission tool ran successfully and committed changes.")

        # Step 5: Clean up branch and clone
        print("🧹 Cleaning up branch and clone...")
        # Checkout original branch (e.g., main or master) before deleting the test branch
        result = run_command(f'git checkout main', cwd=clone_dir)
        if result.returncode != 0:
            print(f"❌ Failed to checkout main branch: {result.stderr}")
            shutil.rmtree(clone_dir)
            return False

        result = run_command(f'git branch -D {branch_name}', cwd=clone_dir)
        if result.returncode != 0:
            print(f"❌ Failed to delete branch {branch_name}: {result.stderr}")
        
        shutil.rmtree(clone_dir)
        print("✅ Test environment cleaned up.")
        return True
        
    except Exception as e:
        print(f"An error occurred during E2E test: {e}")
        return False

if __name__ == "__main__":
    if test_e2e_with_branch():
        print("E2E test PASSED")
        sys.exit(0)
    else:
        print("E2E test FAILED")
        sys.exit(1)
